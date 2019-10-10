# Derived from the Urwid example for lazy directory browser / tree view
# See https://github.com/urwid/urwid/blob/master/examples/browse.py
import urwid
from datamijn.dmtypes import Container, Array, String, ForeignKey, ForeignKeyError
from datamijn.gfx import RGBColor, Palette, Tile

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
                if isinstance(value, String):
                    valuetext += [("string", "\""+str(value)+"\"")]
                elif hasattr(value, 'name'):
                    valuetext += [(body_color, str(value.name))]
                elif isinstance(value, Palette) and len(value) < 32:
                    for color in value:
                        valuetext += text_from_color(color, space=False)
                elif not isinstance(value, Container) and not isinstance(value, Array):
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
                valuetext += [(body_color, f"{type(value).__name__}: {value}")]
            else:
                if isinstance(value, str):
                    body_color = 'string'
                valuetext += text_from_color(value)
                valuetext += [(body_color, repr(value))]
        
        if showtype:
            valuetext += [('blank', ' '), ('type', "<"+type(value).__name__+">")]
        
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
            if isinstance(data, Container):
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
            if isinstance(childdata, Container) or isinstance(childdata, Array) \
              or isinstance(childdata, ForeignKey) or isinstance(childdata, Tile):
                childclass = DatamijnBrowserParentNode
            else:
                childclass = DatamijnBrowserNode
        obj = childclass(childdata, parent=self, key=key, depth=childdepth)
        obj.show_private = self.show_private
        return obj


class DatamijnBrowser():
    palette = [
        ('blank', 'white', 'black'),
        ('body', 'white', 'black'),
        ('name', 'yellow', 'black'),
        ('string', 'light green', 'black'),
        ('foreign', 'light cyan', 'black'),
        ('type', 'dark gray', 'black'),
        ('focus', 'light gray', 'dark blue', 'standout'),
        ('head', 'white', 'dark green', 'standout'),
        ('foot', 'light gray', 'black'),
        ('key', 'light cyan', 'black','underline'),
        ('title', 'white', 'black', 'bold'),
        ('flag', 'dark gray', 'light gray'),
        ('error', 'white', 'dark red'),
    ]

    footer_text = [
        ('title', "Datamijn Data Browser (experimental)"), "    ",
        ('key', "A (align)"),
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
        self.topnode.show_private = True
        self.treewalker = urwid.TreeWalker(self.topnode)
        urwid.connect_signal(self.treewalker, 'modified', self.modified_signal)
        self.listbox = urwid.TreeListBox(self.treewalker)
        self.listbox.offset_rows = 1
        
        header = binary_filename.split("/")[-1]
        self.header = urwid.Text("File: "+header)
        self.footer = urwid.AttrWrap(urwid.Text(self.footer_text),
            'foot')
        self.info = urwid.Text("right")
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
    
    def modified_signal(self):
        obj = self.treewalker.get_focus()[1].get_value()
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
        obj_repr = repr(obj)
        
        if not broken_obj:
            text = [
                ('name', "Path:    "), ('body', obj_path + "\n"),
                ('name', "Type:    "), ('body', "<"+type(obj).__name__+">\n"),
                ('name', "Address: "), ('body', obj_address+"\n"),
                ('name', "Size:    "), ('body', obj_size+"\n"),
            ]
        else:
            text = [
                ('error', "Broken object\n"),
                ('body', obj_error+"\n\n\n")
            ]
        text += [
            ('name', "Value:   "), ('body', (obj_repr[:40]+'...' if len(obj_repr)>43 else obj_repr) + "\n\n"),
        ]
        
        if not broken_obj and self.file and hasattr(obj, "_address") and obj._address != None:
            addresses = []
            sizes = []
            if isinstance(obj, Array) and not isinstance(obj, String):
                # XXX this expects linear arrays.
                for child in obj:
                    if not hasattr(child, '_address'):
                        continue
                    addresses.append(child._address)
                    sizes.append(child._size or 0)
            else:
                addresses.append(obj._address)
                sizes.append(obj._size or 0)
            if self.align_width:
                address = obj._address
            else:
                address = max(obj._address - (obj._address % 0x10) - 0x10, 0)
            self.file.seek(address)
            text.append(('body', 'A' if self.align_width else ' '))
            text.append(('name', f' '*8))
            child_i = 0
            for i in range(16):
                text.append(('name', f'{i: 2x} '))
            text.append(('name', f'\n'))
            for i in range(32):
                text.append(('name', f'{address:08x} '))
                for j in range(16):
                    if address >= self.filesize:
                        text.append(('body', f'.. '))
                    else:
                        if child_i < len(addresses) and address >= addresses[child_i] + sizes[child_i]:
                            child_i += 1
                            if self.align_width and sizes[child_i-1] % 16 != 0:
                                break
                        byte = ord(self.file.read(1))
                        if child_i >= len(addresses) or address < addresses[child_i] or address >= addresses[child_i] + sizes[child_i]:
                            text.append(('body', f'{byte:02x} '))
                        else:
                            text.append(('focus', f'{byte:02x}'))
                            if address == addresses[child_i] + sizes[child_i] - 1:
                                text.append(('body', f' '))
                            else:
                                text.append(('focus', f' '))
                    address += 1
                text.append(('name', '\n'))
        
        self.info.set_text(text)

    def main(self):
        self.screen = urwid.raw_display.Screen()
        self.screen.set_terminal_properties(256)
        self.loop = urwid.MainLoop(self.view, self.palette, screen=self.screen,
            unhandled_input=self.unhandled_input)
        self.loop.run()

    def unhandled_input(self, k):
        if k in ('a', 'A'):
            self.align_width = not self.align_width
            self.modified_signal()
        if k in ('q', 'Q'):
            raise urwid.ExitMainLoop()

