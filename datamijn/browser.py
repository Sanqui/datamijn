# Derived from the Urwid example for lazy directory browser / tree view
# See https://github.com/urwid/urwid/blob/master/examples/browse.py
import urwid
import math
from datamijn.dmtypes import Struct, Array, String, ForeignKey, ForeignKeyError
from datamijn.gfx import RGBColor, Palette, Tile, Image
from datamijn.utils import full_type_name

def text_from_color(value, space=True):
    valuetext = []
    # TODO this obviously only supports 0-31 colors atm.
    if isinstance(value, RGBColor) and value.max == 31:
        r, g, b = value.r//2, value.g//2, value.b//2
        valuetext += [(urwid.AttrSpec('#000', f'#{r:x}{g:x}{b:x}', 256), "  ")]
        if space:
            valuetext += [('body', ' ')]
    return valuetext

class DatamijnBrowserTreeWidget(urwid.TreeWidget):
    def __init__(self, data):
        super().__init__(data)
        self._w = urwid.AttrMap(self._w, 'body', {'name': 'focus', 'body': 'focus', 'string': 'focus', 'foreign': 'focus'})
        if isinstance(data, DatamijnBrowserParentNode):
            self.expanded = data._key is None
            self.update_expanded_icon()
    
    def load_inner_widget(self):
        node = self.get_node()
        value = node.get_value()
        
        name_color = 'name'
        body_color = 'body'
        showtype = True
        broken_value = False
        
        valuetext = []
        
        if hasattr(value, '_error') and value._error and not isinstance(value, Exception):
            valuetext += [('error', ' ')]
        
        if isinstance(node, DatamijnBrowserParentNode):
            if isinstance(value, ForeignKey):
                try:
                    value = value._object
                except ForeignKeyError as ex:
                    value = value
                    body_color = 'error'
                    broken_value = True
                else:
                    body_color = 'foreign'
                valuetext += [(body_color, "→ ")]
            if broken_value:
                valuetext += [(body_color, "(broken)")]
            else:
                if isinstance(value, RGBColor):
                    valuetext += text_from_color(value)
                    valuetext += [(body_color, value.hex)]
                if isinstance(value, String):
                    valuetext += [("string", "\""+str(value)+"\"")]
                elif hasattr(value, 'name'):
                    valuetext += [(body_color, str(value.name))]
                elif isinstance(value, Palette) and len(value) < 32:
                    for color in value:
                        valuetext += text_from_color(color, space=False)
                elif not isinstance(value, Struct) and not isinstance(value, Array):
                    valuetext += [(body_color, repr(value))]
        else:
            if isinstance(value, Tile):
                palette = []
                colors = 1 << value.depth
                for i in range(colors):
                    c = 15 - int(i / (colors-1) * 15)
                    palette.append(urwid.AttrSpec('#000', f'#{c:x}{c:x}{c:x}', 256))
                for y in range(value.height):
                    valuetext.append(('body', ' '))
                    for x in range(value.width):
                        valuetext.append((palette[value.tile[y*value.width+x]], '  '))
                    valuetext.append(('body', '\n'))
                valuetext.pop(-1)
                showtype = False
            elif isinstance(value, Exception):
                body_color = 'error'
                valuetext += [(body_color, f"{type(value).__name__}")]
            else:
                if isinstance(value, str):
                    body_color = 'string'
                valuetext += text_from_color(value)
                valuetext += [(body_color, repr(value))]
        
        if showtype:
            typetext = type(value).__name__
            if len(typetext) > 28:
                typetext = typetext[:28]+"…"
            valuetext += [('blank', ' '), ('type', "<"+typetext+">")]
        
        if node._key is not None:
            text = urwid.Text([(name_color, str(node._key)+": ")] + valuetext)
        else:
            text = urwid.Text(valuetext)
        
        return text
        
    def selectable(self):
        return True

class DatamijnBrowserNode(urwid.TreeNode):
    #def __init__(self, data, browser, **kwargs):
    #    super().__init__(self, data, **kwargs)
    #    self._browser = browser
    
    def load_widget(self):
        return DatamijnBrowserTreeWidget(self)

class DatamijnBrowserParentNode(urwid.ParentNode):
    #def __init__(self, data, browser, **kwargs):
    #    super().__init__(self, data, **kwargs)
    #    self._browser = browser
        
    def load_widget(self):
        return DatamijnBrowserTreeWidget(self)

    def load_child_keys(self):
        def load_keys(data):
            if isinstance(data, Struct):
                #return list(data.keys())
                if self.show_private:
                    return list(data.keys())
                else:
                    return list(key for key in data.keys() if not key.startswith("_"))
            elif isinstance(data, Array):
                return list(range(len(data)))
            elif isinstance(data, Tile):
                return [None]
            elif isinstance(data, ForeignKey):
                try:
                    return load_keys(data._object)
                except ForeignKeyError:
                    return [None]
            else:
                return [None]
        data = self.get_value()
        return load_keys(data)

    def load_child_node(self, key):
        value = self.get_value()
        childdepth = self.get_depth() + 1
        if isinstance(value, Tile):
            childdata = value
            childclass = DatamijnBrowserNode
        elif key == None and isinstance(value, ForeignKey):
            try:
                childdata = value._object
            except ForeignKeyError as ex:
                childdata = ex
            childclass = DatamijnBrowserNode
        else:
            childdata = value[key]
            if isinstance(childdata, Struct) or isinstance(childdata, Array) \
              or isinstance(childdata, ForeignKey) or isinstance(childdata, Tile):
                childclass = DatamijnBrowserParentNode
            else:
                childclass = DatamijnBrowserNode
        obj = childclass(childdata, parent=self, key=key, depth=childdepth)
        obj.show_private = self.show_private
        return obj

class HexViewerChild():
    def __init__(self, address, size, name=None, type=None, nested=False):
        self.address = address
        self.size = size or 0
        self.end_address = self.address + self.size
        self.name = str(name) if name != None else None
        self.type = type
        self.nested = nested

class DatamijnBrowser():
    palette = [
        ('blank', 'white', 'black'),
        ('body', 'white', 'black'),
        ('name', 'yellow', 'black'),
        ('string', 'light green', 'black'),
        ('foreign', 'light cyan', 'black'),
        ('type', 'dark gray', 'black'),
        ('focus', 'light gray', 'dark blue', 'standout'),
        ('focus_pointer', 'light gray', 'dark magenta', 'standout'),
        ('focus_key', 'light gray', 'dark cyan', 'standout'),
        ('head', 'white', 'dark green', 'standout'),
        ('foot', 'light gray', 'black'),
        ('key', 'light cyan', 'black','underline'),
        ('key_invert', 'black', 'light cyan','underline'),
        ('title', 'white', 'black', 'bold'),
        ('flag', 'dark gray', 'light gray'),
        ('error', 'white', 'dark red'),
    ]

    footer_text = [
        ('title', "Datamijn Data Browser (experimental)"), "   ",
        ('key_invert', "A"),
        ('key', " align "),
        ('key_invert', "E"),
        ('key', " explain "),
        ('key_invert', "["),
        ('key', "/"),
        ('key_invert', "'"),
        #('key', "UP"), ",", ('key', "DOWN"), ",",
        #('key', "PAGE UP"), ",", ('key', "PAGE DOWN"),
        #"  ",
        #('key', "+"), ",",
        #('key', "-"), "  ",
        #('key', "LEFT"), "  ",
        #('key', "HOME"), "  ",
        #('key', "END"), "  ",
        #('key', "Q"),
    ]

    def __init__(self, data=None, file=None, binary_filename="", show_private=False):
        self.file = file
        self.file.seek(0)
        self.file.read()
        self.filesize = self.file.tell()
        print(self.filesize)
        
        self.topnode = DatamijnBrowserParentNode(data)
        self.topnode.show_private = show_private
        self.treewalker = urwid.TreeWalker(self.topnode)
        urwid.connect_signal(self.treewalker, 'modified', self.modified_signal)
        self.listbox = urwid.TreeListBox(self.treewalker)
        self.listbox.offset_rows = 1
        
        header = binary_filename.split("/")[-1]
        self.header = urwid.Text("File: "+header)
        self.footer = urwid.AttrWrap(urwid.Text(self.footer_text),
            'foot')
        self.info = urwid.Text("right", wrap='clip')
        self.view = urwid.Columns([
            urwid.Frame(
                urwid.AttrWrap(self.listbox, 'body'),
                header=urwid.AttrWrap(self.header, 'head'),
                footer=self.footer
            ), 
            urwid.Filler(
                urwid.AttrWrap(self.info, 'body'),
                valign='top',
                top=0
            )
        ])
        
        self.align_width = False
        self.explain = False
        self.scroll_hex = 0
        self.last_obj = None
        
        self.modified_signal()
    
    def modified_signal(self):
        obj = self.treewalker.get_focus()[1].get_value()
        
        if obj != self.last_obj:
            self.scroll_hex = 0
        
        broken_obj = False
        obj_error = ""
        try:
            obj_path = ".".join(str(x) for x in obj._path) if hasattr(obj, "_path") else "?"
        except ForeignKeyError as ex:
            broken_obj = True
            obj_error = f"{type(ex).__name__}: {ex}"
        if not broken_obj:
            obj_address = hex(obj._address) if hasattr(obj, "_address") else "?"
            obj_size = (hex(obj._size) if obj._size != None else "-") if hasattr(obj, "_size") else "?"
            obj_size_extra = (hex(obj._size_extra) if obj._size_extra != None else "") if hasattr(obj, "_size_extra") else ""
            if obj_size_extra:
                obj_size = obj_size + " + " + obj_size_extra
            
            obj_pointer = obj._pointer if hasattr(obj, "_pointer") else None
            obj_key = obj._key if hasattr(obj, "_key") else None
            obj_trace = obj._trace if hasattr(obj, "_trace") else None
        obj_repr = repr(obj)
        
        if not broken_obj:
            type_color = 'error' if isinstance(obj, Exception) else 'body'
            text = [
                ('name', "Path:    "), ('body', obj_path + "\n"),
                ('name', "Type:    "), (type_color, ""+full_type_name(type(obj))+"\n"),
                ('name', "Address: "), ('body', obj_address+"\n"),
                ('name', "Size:    "), ('body', obj_size+"\n"),
                ('name', "Trace:   "), ('body', str(obj_trace)+"\n"),
            ]
            if obj_pointer:
                text += [('name', "Pointer: "), ('body', repr(obj_pointer)+f" <{type(obj_pointer).__name__}>\n")]
            elif obj_key:
                text += [('name', "Key:     "), ('body', repr(obj_key)+f" <{type(obj_key).__name__}>\n")]
            else:
                text.append('\n')
        else:
            text = [
                ('error', "Broken object\n"),
                ('body', obj_error+"\n\n\n\n")
            ]
        
        if isinstance(obj, Exception):
            text += ('error', type(obj).__name__), ('body', f": {obj}"),
        else:
            text += [
                ('name', "Value:   "), ('body', (obj_repr[:40]+'...' if len(obj_repr)>43 else obj_repr) + "\n"),
            ]
        
            if hasattr(obj, '_error') and obj._error:
                text += [('error', 'Substructure has error\n')]
            else:
                text += ["\n"]
        
        if isinstance(obj, Image):
            palette = obj._palette
            tilewidth = obj._child_type._child_type.width
            width = tilewidth*len(obj[0])
            height = obj._child_type._child_type.height*len(obj)
            for y in range(height):
                text += [('body', ' ')]
                for x in range(width):
                    #value = obj[y//8][tilex].tile[(y%8) * 8 + tilewidth]
                    value = obj[y//8][x//8].tile[(y%8) * 8 + (x % 8)]
                    text += [text_from_color(palette[value], space=False)]
                text += [('body', '\n')]
        
        if not broken_obj and self.file and ((hasattr(obj, "_address") and obj._address != None) or hasattr(obj, '_trace') or hasattr(obj, '_key') or isinstance(obj, Array)) and not isinstance(obj, Exception):
            childs_at = {}
        
            def get_childs_from(obj, name, type='', nested=0):
                if isinstance(obj, Array) and not nested:
                    for i, child in enumerate(obj):
                        get_childs_from(child, f"{name} {i}".strip(), nested=nested+1)
                else:
                    if hasattr(obj, '_address'):
                        if not (nested and obj._address in childs_at):
                            childs_at[obj._address] = HexViewerChild(obj._address, obj._size, name, type=type, nested=nested+1)
                if hasattr(obj, '_trace'):
                    for param in obj._trace.params:
                        if len(obj._trace.params) > 1:
                            if name.endswith('⁻ⁿ'):
                                child_name = name
                            elif name.endswith('⁻¹'):
                                child_name = f"{name[:-2]}⁻ⁿ"
                            else:
                                child_name = f"{name}⁻¹"
                        else:
                            child_name = name
                        get_childs_from(param, child_name, type=type, nested=nested+1)
                if hasattr(obj, '_pointer') and hasattr(obj._pointer, '_address'):
                    if not (nested and obj._pointer._address in childs_at):
                        childs_at[obj._pointer._address] = HexViewerChild(obj._pointer._address, obj._pointer._size, f"{name} @", type="pointer", nested=nested+1)
                if hasattr(obj, '_key'):
                    get_childs_from(obj._key, f"{name} ->", type="key")
                if hasattr(obj, '_match_value'):
                    get_childs_from(obj._match_value, f"{name} &", type="key")
        
            if isinstance(obj, ForeignKey):
                obj = obj._object
            elif isinstance(obj, Struct):
                for name, child in obj.items():
                    get_childs_from(child, name)
            else:
                get_childs_from(obj, '')
            
            obj2 = obj
            while hasattr(obj2, '_trace'):
                obj2 = obj2._trace.params[0]
            
            # hotfix
            if hasattr(obj2, '_address'):
                start_address = obj2._address
            elif childs_at:
                start_address = min(childs_at)
            else:
                start_address = 0
            
            if self.align_width:
                address = start_address
                address += self.scroll_hex
            else:
                address = max(start_address - (start_address % 0x10) - 0x10, 0)
                address += self.scroll_hex*0x10
            if address < 0:
                address = 0
            last_child = None
            cur_child = None
            self.file.seek(address)
            text.append(('key_invert', 'A') if self.align_width else ' ')
            text.append(('key_invert', 'E') if self.explain else ' ')
            text.append(('name', f' '*8))
            child_i = 0
            for i in range(16):
                text.append(('name', f'{i: 2x} '))
                if i == 7:
                    text.append(' ')
            text.append(('name', f'\n'))
            continue_focus = None
            
            for i in range(40):
                text.append(('name', f'{address:08x} '))
                text.append((continue_focus or 'body', f' '))
                line = []
                explain_names = []
                for j in range(16):
                    if address >= self.filesize:
                        line.append(('body', f'.. '))
                    else:
                        if cur_child and address >= cur_child.end_address:
                            last_child = cur_child
                            cur_child = None
                            if self.align_width and last_child.size % 16 != 0:
                                break
                        if address in childs_at and (not cur_child or cur_child.nested <= childs_at[address].nested):
                            last_child = cur_child
                            cur_child = childs_at[address]
                            if self.explain and cur_child.name:
                                explain_names.append((j, cur_child.name))
                            if not cur_child.size:
                                last_child = cur_child
                                cur_child = None
                        byte = ord(self.file.read(1))
                        space = '  ' if j == 7 else ' '
                        if not cur_child:
                            line.append(('body', f'{byte:02x}{space}'))
                            continue_focus = None
                        else:
                            continue_focus = 'focus' + (f"_{cur_child.type}" if cur_child.type else "")
                            line.append((continue_focus, f'{byte:02x}'))
                            if address == cur_child.end_address-1:
                                line.append(('body', space))
                                continue_focus = None
                            else:
                                line.append((continue_focus, space))
                                continue_focus = continue_focus
                    address += 1
                line.append(('body', '\n'))
                if self.explain:
                    explain_columns = [j for j, n in explain_names]
                    
                    explain_rows = []
                    last_col = None
                    for j, explain_name in reversed(explain_names):
                        col = j*3 + (j==7)
                        if last_col == None or col + len(explain_name)+1 - (j==7) > last_col:
                            explain_rows.append([])
                        explain_rows[-1].append((j, explain_name))
                        last_col = col
                    
                    for row in explain_rows:
                        line += [
                            ('body', " "*10)
                        ]
                        last_j = 0
                        for j, explain_name in reversed(row):
                            col_str = ""
                            for j2 in range(last_j, j):
                                space = " " if j2==7 else ""
                                if j2 in explain_columns:
                                    line += "|  " + space
                                else:
                                    #line += f"{j2:x}  " + space
                                    line += f"   " + space
                            namepadlen = (3 - ((len(explain_name)+1) % 3)) % 3
                            if j == 7: namepadlen += 1
                            line += [
                                "`",
                                ('name', explain_name + " "*namepadlen)
                            ]
                            last_j = j + (len(explain_name)+1+namepadlen) // 3
                        line.append(('body', '\n'))
                text += line
        
        self.info.set_text(text)
        
        self.last_obj = obj

    def main(self):
        self.screen = urwid.raw_display.Screen()
        self.screen.set_terminal_properties(256)
        self.loop = urwid.MainLoop(self.view, self.palette, screen=self.screen,
            unhandled_input=self.unhandled_input)
        self.loop.run()

    def unhandled_input(self, k):
        if k in ('a', 'A'):
            self.scroll_hex = 0
            self.align_width = not self.align_width
            self.modified_signal()
        if k in ('e', 'E'):
            self.explain = not self.explain
            self.modified_signal()
        if k in ('q', 'Q'):
            raise urwid.ExitMainLoop()
        if k in ('[',):
            self.scroll_hex -= 1
            self.modified_signal()
        if k in ('\'',):
            self.scroll_hex += 1
            self.modified_signal()
            
            

