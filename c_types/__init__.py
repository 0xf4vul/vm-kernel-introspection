# -*- coding: utf-8 -*-
import re
import memory

KERNEL_PAGE_OFFSET = memory.get_defines()[0]

#at which depth level do we stop recursing:
MAX_DEPTH=5

#iters = 0

def _new_id(type_list):
    "Generate a new unique type id for the type list. random bruteforce approach"
    import random
    while 1:
      x = random.randint(0,2**31)
      if x not in type_list: return x

#def new_type(type_list, *args, **kwargs):
    #"hilfsfunktion zum erstellen des dicts für einen neuen typ"
    #kwargs['id'] = _new_id(type_list)
    #return kwargs

class Type:
    "BaseClass for all Types"
    name = None
    base = None

    def get_base(self):
	"""
	for convenient user access
	returns a Type instance of this type’s base-type.
	e.g. a Pointer to a Struct would have a base-type of Struct
	"""
	if self.base in self.type_list:
	      return self.type_list[self.base]
    def resolve(self, loc=None, depth=MAX_DEPTH):
	"""
	resolve the type

	Some types are just intermediate Types that reference another Type
	through the base property. E.g a Variable is a type on its own but
	has a base-Type which is the Type of the Variable.

	resolve() iterates until such a base-type is found.
	"""
	return (self, loc)
    
    def value(self, loc, depth=MAX_DEPTH):
        """
	assume memory at location loc is of our type

	tries to return a python-like representation of the object
	"""
	if depth == 0: return UnresolvedException(self, loc)
	if self.base is not None:
	    return self.type_list[self.base].value(loc, depth-1)
	return None

    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	try:
		if seen[self] != None:
			if loc in seen[self]:
				return True
	except KeyError, e:
		pass

	if self.base is not None:
		try:
			if seen[self] != None:
				seen[self].add(loc)
		except KeyError, e:
			seen[self] = set([loc])
		return self.type_list[self.base].memcmp(loc, loc1, depth-1, seen)
	return True

    def register(self):
	"if this type is manually added, make it is also registered with a valid id in the global type register"
	self.id = _new_id(self.type_list)
	self.type_list[self.id] = self
    def get_name(self):
	"""
	returns a likely name for the type by iterating through the Types base-types
	returns "void" if none is available
	"""
	name = self.name
	base = self.base
# is this an error? Or should it be fixed like i suggested in the comment
# KeyErrors may not happen and indicate an error in the data model, so
# we should rather fix the model, but nothing here
	while not name and base is not None:
	    name = self.type_list[self.base].name
	    if base == self.type_list[self.base].base: break
	    base = self.type_list[self.base].base
	return name if name else "undef"

    def __repr__(self):
	return "<%s instance '%s'>" % (self.__class__, self.get_name())
	
    def bases(self):
	"iterate over all base-types"
	t = self
	while t.base is not None and t.base in self.type_list:
	  t = self.type_list[t.base]
	  yield t

class UnresolvedException(Exception):
  def __init__(self, type, loc):
    self.type = type
    self.loc  = loc
    Exception.__init__(self, "unresolved type %s at 0x%x" % (repr(type), loc))

class Void(Type):
    "A None Type that is used for void * or other types with missing base-information"
    def __init__(self, type_list):
	"creates this type and adds it to the type_list"
	self.type_list = type_list
	self.id = 0
	self.type_list[self.id] = self
	self.name = "void"
    def get_base(self):
	return None
    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	return None
    def value(self, loc, depth=MAX_DEPTH):
	return None
    
class SizedType(Type):
    "This is a Type with size-information associated"
    size = 0

class Struct(SizedType):
    "This type represents a C-structure. Its members usually have the type Member"
    def append(self, type):
	"adds a new member"
	self.members.append(type.id)
    
    def value(self, loc, depth=MAX_DEPTH):
	"returns a dictionary filled with this struct’s member’s values"
	if depth == 0: return UnresolvedException(self, loc)
	
	out = {}
	if loc == 0:
	    return NullPointerException(repr(self))
	
        for real_member, member_loc in self.__iter__(loc):
	    try:
		out[real_member.get_name()] = real_member.value(member_loc, depth-1)
	    except MemoryAccessException, e:
		out[real_member.get_name()] = e
	    #member, member_loc = real_member.resolve(member_loc, depth-1)
	    #if member_loc == 0: #prevent NullPointerExceptions
	      #value = None
	    #else:
	      #value = member.value(member_loc, depth-1)
	    #name_str = real_member.name and real_member.name or ("member_%x" % real_member.offset)
	    #out[name_str] = value
        return out

    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
        iseq = True
	try:
		if seen[self] != None:
			if loc in seen[self]:
				return True
	except KeyError, e:
		pass
	
	i = 0
	for real_member, member_loc in self.__iter__(loc):
            member, member_loc = real_member.resolve(member_loc, depth-1)
	    if hasattr(self, "members"):
	    	ind = self.members[i]
	    	real_member1 = self.type_list[ind]
	    	member_loc1 = loc1 + self.type_list[ind].offset
	    elif hasattr(self, "entries"):
		name, offset = (self.entries.items())[i]
		real_member1, member_loc1 = self.parent(resolve_pointer(loc1+offset))
	    else:
		raise RuntimeError("not a struct and not a linked list")
	    member1, member_loc1 = real_member1.resolve(member_loc1, depth-1)
            if member_loc == 0 or member_loc1 == 0:
		i += 1
                continue
	    try:
		    if seen[self] != None:
			    seen[self].add(loc)
	    except KeyError, e:
		    seen[self] = set([loc])
            r = member.memcmp(member_loc, member_loc1, depth-1, seen)
            if not r:
                iseq = False
                break
	    i += 1
        return iseq
        
    def __getitem__(self, item, loc=None):
        """
	returns the Type of this Structs member named item.
	returns None if no such member exists

	if loc is set, returns (member_type, member_location)
	"""
	for i in self.members:
	  if self.type_list[i].name == item:
	    item = self.type_list[i]
	    if loc is None:
	      return item
	    else:
	      return item, loc + item.offset
    def __iter__(self, loc=None):
	"iterate over all Members, if loc is set, yields (member_type, member_location)"
	for i in self.members:
	  if loc is None:
	    yield self.type_list[i]
	  else:
	    yield self.type_list[i], loc + self.type_list[i].offset

class Union(Struct):
    "This type represents a C-union which is basically a Struct where all members have the offset 0."
    def __str__(self, depth=MAX_DEPTH):
        return "union %s {\n%s}" % (self.get_name(), self.stringy(depth))
    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	return True

class Array(Type):
    "Represents an Array. Including the upper bound"
    bound = None
    def __init__(self, info, bound=None):
	"Creates an Array with bound number of elements of Type info"
	self.base = info.id
	self.type_list = info.type_list
	self.bound = bound
	self.register()
	
    def __str__(self,depth=MAX_DEPTH):
        return "<Array[%s] %s>" % (self.bound, self.get_name())
	
    def value(self, loc, depth=MAX_DEPTH):
	"returns a sequence of all elements"
	if depth == 0: return UnresolvedException(self, loc)
	
	ret = []
	for member, member_loc in self.__iter__(loc, depth):
	  ret.append( member.value(member_loc, depth-1) )

	return ret

    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	    try:
		    if seen[self] != None:
			    if loc in seen[self]:
				    return True
	    except KeyError, e:
		    pass

	    iseq = True
	    i = 0
	    # this is a dirty hack to iterate over members in both
	    # memory images at the same time
	    for member, member_loc in self.__iter__(loc, depth):
		    member1, member_loc1 = self.__getitem__(i, loc1, depth)
		    try: 
			    if seen[self] != None:
				    seen[self].add(loc)
		    except KeyError, e:
			    seen[self] = set([loc])
		    r = member.memcmp(member_loc, member_loc1, depth-1, seen)
		    if not r:
			    iseq = False
			    break
		    i += 1
	    return iseq

    def get_element_size(self):
	"iterate on base-types and return the first one with size-information or None if no size seems to be known"
	#TODO cache this information for better performance
	base =  self.type_list[self.base]
	while not hasattr(base, "size"):
	    if base.base is None:
		return None
	    base = self.type_list[base.base]
	  #try:
	  	#base = self.type_list[base.base]
	  #except KeyError:
		#print "array with no size"
		#raise RuntimeError
	return base.size
	
    def __getitem__(self, idx, loc=None, depth=MAX_DEPTH):
	if self.bound and (idx < 0 or idx >= self.bound):
	  raise IndexError("%d out of array bound %d (%s)" % (idx, self.bound, self))
	if loc is None:
	  return self.type_list[self.base]
	size = self.get_element_size()
	return self.type_list[self.base], loc + size * idx
	
    def __iter__(self, loc=None, depth=MAX_DEPTH):
	if self.bound is None:
	  yield self.__getitem__(0, loc, depth)
	  return
	for i in range(0, self.bound):
	  yield self.__getitem__(i, loc, depth)
	  
    def __len__(self):
	return self.bound+1 if self.bound else 0
	
    def __nonzero__(self):
	"needs to be overriden, as the object might be nonzero (i.e. not None) even though __len__() returns 0"
	return True

class Subrange(Type):
    "ArraySubrange-Type for use with Array. Holds bounds information"
    bound = None

class Function(Type):
    def __str__(self, depth=MAX_DEPTH):
        return "%s()" % self.get_name()
    def value(self, loc, depth=MAX_DEPTH):
	"returns a callable function object"
	return KernelFunction(loc, type)
    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	return True

class KernelFunction:
    def __init__(self, location, type):
      self.location = location
      self.type = type
    def __call__(self):
      raise Exception("Unimplemented. Cannot yet call kernel functions")

class RecursingTypeException(RuntimeError):
  pass
class MemoryAccessException(RuntimeError):
  pass
class NullPointerException(MemoryAccessException):
  pass
class UserspaceVirtualAddressException(MemoryAccessException):
  pass
class PageNotPresent(MemoryAccessException):
  pass

base_type_to_memory = {'int-5': 5, 'char-6': 1, 'None-7': 6, 'long unsigned int-7': 6, 'unsigned int-7': 4, 'long int-5': 7, 'short unsigned int-7': 2, 'long long int-5': 7, 'signed char-6': 1, 'unsigned char-8': 0, 'short int-5': 3, 'long long unsigned int-7': 6, '_Bool-2': 11, 'double-4': 8}

class BaseType(SizedType):
    """
    This is for real base-types like unsigned int
    
    encodings:
    2	(boolean)
    4	(float)
    5	(signed)
    6	(signed char)
    7	(unsigned)
    8	(unsigned char)
    
    10	(string)
    """
    encoding = 0

    @staticmethod
    def get_value(loc, mem_type=6, info=None, image=0): #unsigned long int
	"""
	uses the memory module to access physical memory
	returns a representation based on mem_type
	loc is a virtual address

	may raise a MemoryAccessException
	"""
	if loc < 4096: raise NullPointerException(loc, repr(info))

	# check if we have a userspace address
	# for 2.6.11 kernels this is 0xffff810000000000UL
	# since 2.6.27 this is 0xffff880000000000UL
	# if loc < 0xffff880000000000:
	if loc < KERNEL_PAGE_OFFSET:
		# this is a userspace virtual address!
		raise UserspaceVirtualAddressException("userspace paging not implemented!", loc, str(info))
	try:
		physloc = memory.virt_to_phys(loc, image)
		return memory.access(mem_type, physloc, image)
	except ValueError, e:
		raise PageNotPresent("page not present")
	except RuntimeError, e:
		raise MemoryAccessException(e.args + (loc, repr(info)))

    def value(self, loc, depth=MAX_DEPTH):
        "try to access memory at location loc and return its value"
	try:
	  return self.get_value(loc, base_type_to_memory["%s-%d" % (self.name, self.encoding)], info=self)
	except MemoryAccessException, e:
	  return e

    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	try:
		if seen[self] != None:
			if loc in seen[self]:
				return True
	except:
		pass
	try:
		val1 = self.get_value(loc,  base_type_to_memory["%s-%d" % (self.name, self.encoding)], info=self, image=0)
		val2 = self.get_value(loc1, base_type_to_memory["%s-%d" % (self.name, self.encoding)], info=self, image=1)
		return val1 == val2
	except MemoryAccessException, e:
		return (self.name, e)

class Enum(SizedType):
    enums = {}
    def append(self, enum):
        self.enums[enum.name] = enum.const
    #TODO...
class Enumerator(Type):
    def __init__(self, info, type_list):
        Type.__init__(self, info, type_list)
        self.const = int(info["const_value"])
    def __str__(self):
        return "%d (%s)" % (self.const, self.name)
            
class Variable(Type):
    def resolve(self, loc=None, depth=MAX_DEPTH):
	return self.type_list[self.base].resolve(loc, depth)
#    def value(self, loc, depth=MAX_DEPTH):
#	return self.type_list[self.base].value(loc, depth)
    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	try:
		if seen[self] != None:
			if loc in seen[self]:
				return True
	except KeyError, e:
		pass
	try:
		if seen[self] != None:
			seen[self].add(loc)
	except KeyError, e:
		seen[self] = set([loc])
	return self.type_list[self.base].memcmp(loc, loc1, depth, seen)

class Const(Variable):
    pass

class Member(Variable):
    "This is a StructureMember"
    offset = 0

class Pointer(BaseType):
    "Represents a Pointer to another type"
    def __init__(self, info):
	"Creates a Pointer pointing to memory of type info"
	self.base = info.id
	self.type_list = info.type_list
	self.register()
	
    def resolve(self, loc=None, depth=MAX_DEPTH):
	_loc = loc
	if _loc is not None:
	    try:
		_loc = self.get_value(loc, info=self) # unsigned long
	    except (UserspaceVirtualAddressException, NullPointerException), e:
		return (self, loc)
	
	if self.base is not None and _loc != 0:
	      return self.type_list[self.base].resolve(_loc, depth-1)
	else:
	      return (self, loc)
    def get_type_name(self):
	if self.base is not None:
	  return "%s *" % self.type_list[self.base].get_name()
	return "undef *"
	
    def get_pointer_address(self, loc):
	"""
	returns an integer with the memory address to which the pointer
	at location loc points
	"""
	return self.get_value(loc, info=self)

    def value(self, loc, depth=MAX_DEPTH):
	if depth == 0: return UnresolvedException(self, loc)

	try:
	  ptr = self.get_value(loc, info=self) # unsigned long
	except MemoryAccessException, e:
	  return e
	
	if self.base is not None and ptr != 0:
	      return self.type_list[self.base].value(ptr, depth-1)
	return None

    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	try:
		if seen[self] != None:
			if loc in seen[self]:
				return True
	except KeyError, e:
		pass

	ptr = self.get_value(loc)
	ptr1 = self.get_value(loc1, image=1)
	
	if ptr == ptr1 == 0:
		return True
	if ptr == 0 or ptr1 == 0:
		return False

	if self.base is not None and ptr != 0:
		try: 
			if seen[self] != None:
				seen[self].add(loc)
		except KeyError, e:
			seen[self] = set([loc])
		return self.type_list[self.base].memcmp(ptr, ptr1, depth-1, seen)
	else:
		return True

class Typedef(Type):
    def resolve(self, loc, depth=MAX_DEPTH):
	if depth > 20: raise RecursingTypeException("recursing type...")
	return self.type_list[self.base].resolve(loc, depth-1)
#    def value(self, loc, depth=MAX_DEPTH):
#	return self.type_list[self.base].value(loc, depth-1)
    def memcmp(self, loc, loc1, depth=MAX_DEPTH, seen={}):
	try:
		if seen[self] != None:
			if loc in seen[self]:
				return True
	except KeyError, e:
		pass
	try:
		if seen[self] != None:
			seen[self].add(loc)
	except:
		seen[self] = set([loc])
	return self.type_list[self.base].memcmp(loc, loc1, depth-1, seen)

resolve_pointer   = lambda loc: BaseType.get_value(loc)

class UnwantedType(Type):
    pass
