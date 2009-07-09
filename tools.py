# -*- coding: utf-8 -*-
# implementation of tool-functions for convenient use

from c_types import *
from c_types.user_types import *

from memory_manager import *

#type_of_address = lambda y: types[memory[y]]
cast = lambda memory, type: Memory(memory.get_loc(), type)
type_of = lambda name: types[names[name]]
pointer_to = lambda name: Pointer(type_of(name), types)
kernel_name = lambda name: Memory(*addresses[name])

def handle_array(array, member, struct, cls):
  """Replacing struct list_heads is difficult for Arrays
  So here we implement the special handling for this case.
  
  We create a pseudo member element for each array idx
  and then transform it into a KernelLinkedList that gets
  appended to the original data structure.
  Finally the obsolete array is removed from there"""
  
  idx = 0
  for entry,offset in array.__iter__(loc=0):
    pseudo_member = Type()
    pseudo_member.name = "%s_%d" % (member.name, idx)
    pseudo_member.offset = member.offset + offset
    new_element = cls(struct, pseudo_member)
    new_element.register()
    struct.append(new_element)
    idx += 1
  struct.members.remove(member.id)
  #cannot delete it because it might be referenced by other structs!
  #del types[member.id]

def prepare_list_heads():
  """kernel lists are a special thing and need special treatment
  this routine replaces all members of type struct list_head with
  an appropriate replacement that takes care handling these lists"""
  
  member_list = []
  array_handlers = []
  for k,v in types.iteritems():
    if isinstance(v, Struct):
      for member in v:
	lh = member.get_base()
	if lh and lh.name:
	  if lh.name == "list_head":
	    member_list.append((KernelDoubleLinkedList(v, member), member))
	if isinstance(lh, Array) and lh.get_base():
	  ar_lh = lh.get_base()
	  if ar_lh.name == "list_head":
	    array_handlers.append((lh, member, v, KernelDoubleLinkedList))

  for val in array_handlers:
    handle_array(*val)
	  
  for new_member, old_member in member_list:
      new_member.takeover(old_member)

def init(filename=None):
    "helper function to initialise a dump-session, filename is the path to the memory dump e.g /dev/mem"
    import memory, type_parser
    global types, names, addresses
    if filename is not None:
	memory.map(filename, 20000)
    types, memory = type_parser.load(open("data.dumpc"))

    names = {}
    for k,v in types.iteritems():
      names[v.name] = k

    addresses = {}
    for k,v in memory.iteritems():
      addresses[types[v].name] = (k, types[v])

    #some more cleanup i forgot once. is already obsolete…
    pat3= re.compile('DW_OP_plus_uconst: (\d+)')
    for k,v in types.iteritems():
	if hasattr(v, "offset") and type(v.offset) != int:
	    v.offset = int(pat3.search(v.offset).group(1))
    
    #load_additional_symbols()
    prepare_list_heads()

    return names, types, addresses

def strings(phys_pos, filename):
  import memory
  f = open(filename, "w")
  while 1:
    s = memory.access(10, phys_pos)
    print >>f, "%08x\t%s" % (phys_pos, repr(s))
    phys_pos += len(s) + 1

def load_additional_symbols():
  pgt = kernel_name('__ksymtab_init_task') #first element
  syms = cast(pgt, Array(pgt.get_type()))
  i = 0
  try:
   while 1:
    name, value = str(cast(syms[i].name, Pointer(String(Array(type_of('unsigned char')))))), hex(syms[i].value)
    if not name in addresses and name in names: addresses[name] = (int(syms[i].value), type_of(name))
    i += 1
  except: pass

def dump_pagetables(pgt4, filename):
  f = open(filename, "w")
  page = lambda x: (x & ~0x8000000000000fff) + 0xffff880000000000
  is_null = lambda x: x.get_loc() == 0xffff880000000000
  loc  = lambda x: x.get_loc() - 0xffff880000000000
  for i in range(512):
    pud = Memory( page(pgt4[i].pgd.get_value()[1]), type_of('level3_kernel_pgt')) #raw addresses
    if not is_null(pud):
      print >>f, "  [%03d] --> %x" % (i, loc(pud))
      for j in range(512):
	pmd = Memory( page(pud[j].pud.get_value()[1]), type_of('level2_kernel_pgt'))
	if not is_null(pmd):
	  print >>f, "     [%03d] --> %x" % (j, loc(pmd))
	  for k in range(512):
	    pte = Memory( page(pmd[k].pmd.get_value()[1]), type_of('level2_kernel_pgt'))
	    if not is_null(pte) and pmd[k].pmd.get_value()[1] & 0x80 == 0: #skip LARGE PAGES for now
	      print >>f, "        [%03d] --> %x" % (k, loc(pte))
	      for l in range(512):
		if pte[l].pmd.get_value()[1] != 0:
		  print >>f, "           [%03d] --> %x" % (l, pte[l].pmd.get_value()[1])
  f.close()