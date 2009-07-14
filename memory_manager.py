# -*- coding: utf-8 -*-
from c_types.extensions import string
from c_types import *
class Memory:
    """Memory Manager

Holds typed and addressed information, resolves structures and makes members accessible

Members are conveniently accessable:
  sample = Memory(location, type)
  print sample.member1
  print sample.array_member[1]
  print len(sample.array_member)
  [i**2 for i in sample.array_member]
  [member.get_type().get_name() for member in sample]
"""
    def __init__(self, loc, type):
	"initialise this MemoryManager. Its of type type at location loc"
	self.__loc = loc
	self.__type = type
    def get_type(self):
	"returns a c_types-instance associated with this Memory-object"
	return self.__type
    def get_loc(self):
	"returns the location associated with this Memory-object"
        return self.__loc
    def get_value(self):
	"returns the representation presented by this Memory’s type and location"
        return self.__value()
    def __value(self):
        #type, loc = self.type.resolve(self.loc)
        #return type.value(loc)
        return self.__type.value(self.__loc)[1]
    def __iseq(self, other):
	return 
    def resolve(self):
	"resolves this Type (see c_types.Type.resolve) and returns a new Memory-object"
	this, loc = self.__type.resolve(self.__loc)
	return Memory(loc, this)
    #    retval = self.get_type().value(self.get_loc())
    #    return retval
#    def __int__(self):
#        retobj = self.__type.value(self.__loc)
#        typename = type(retobj).__name__
#        if(typename != 'int' and typename != 'long'):
#            raise TypeError("%s is not of type int it is of type %s" % (repr(self), type(retobj)))
#        return retobj
#    def __float__(self):
#        retobj = self.__type.value(self.__loc)
#        typename = type(retobj).__name__
#        if(typename != 'float' and typename != 'double'):
#            raise TypeError("%s is not of type float it is of type %s" % (repr(self), type(retobj)))
#        return retobj
    def __getattr__(self, key):
        this, loc = self.__type.resolve(self.__loc)
        # print key, repr(this), loc, hex(loc)
	
        if not isinstance(this, Struct): return None
	member, location = this.__getitem__(key, loc)
	if member is None: raise KeyError("%s has no attribute %s" % (repr(this), key))
        return Memory(location, member)
        
    def __getitem__(self, idx):
	this, loc = self.__type.resolve(self.__loc)
	if not isinstance(this, Array): return None
	if this.bound and idx > this.bound: raise IndexError("out of bounds")
	type = this.type_list[this.base]
	size_type = type
	while not hasattr(size_type, "size"):
	  size_type = this.type_list[size_type.base]
	return Memory(loc + idx * size_type.size, size_type)
    def __iter__(self):
	this, loc = self.__type.resolve(self.__loc)
	if isinstance(this, Struct):
	    for member, location in this.__iter__(loc):
		yield Memory(location, member)
	elif isinstance(this, Array):
	    type = this.type_list[this.type.base]
	    size_type = type
	    while not hasattr(size_type, "size"):
		size_type = this.type_list[size_type.base]
	    for idx in range(this.bound):
		yield Memory(loc + idx * size_type.size, size_type)
    def __len__(self):
	this, loc = self.__type.resolve(self.__loc)
	if not isinstance(this, Array): return None
	return len(this)
    def __str__(self):
	return str(self.__value())
    def __int__(self):
	return int(self.__value())
    def __hex__(self):
	return hex(self.__value())
    def __float__(self):
	return float(self.__value())
    def __repr__(self):
	return "<Memory %s @0x%x>" % (repr(self.__type), self.__loc)
    def memcmp(self):
#        return self.__type.memcmp(self.__loc, 0, set([]))
        return self.__type.memcmp(self.__loc, self.__loc, 0, {})
