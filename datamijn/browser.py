# Derived from the Urwid example for lazy directory browser / tree view
# See https://github.com/urwid/urwid/blob/master/examples/browse.py
import urwid
from datamijn.dmtypes import Container, Array, String, ForeignKey
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
        
        valuetext = []
        if isinstance(node, DatamijnBrowserParentNode):
            if isinstance(value, ForeignKey):
                #name_color = 'name_foreign'
                body_color = 'foreign'
                valuetext += [(body_color, "→ ")]
                value = value._object
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
    def load_widget(self):
        return DatamijnBrowserTreeWidget(self)

class DatamijnBrowserParentNode(urwid.ParentNode):
    def load_widget(self):
        return DatamijnBrowserTreeWidget(self)

    def load_child_keys(self):
        def load_keys(data):
            if isinstance(data, Container):
                #return list(data.keys())
                return list(key for key in data.keys() if not key.startswith("_"))
            elif isinstance(data, Array):
                return list(range(len(data)))
            elif isinstance(data, Tile):
                return [None]
            elif isinstance(data, ForeignKey):
                return load_keys(data._object)
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
            childdata = value._object
            childclass = DatamijnBrowserNode
        else:
            childdata = value[key]
            if isinstance(childdata, Container) or isinstance(childdata, Array) \
              or isinstance(childdata, ForeignKey) or isinstance(childdata, Tile):
                childclass = DatamijnBrowserParentNode
            else:
                childclass = DatamijnBrowserNode
        return childclass(childdata, parent=self, key=key, depth=childdepth)


class DatamijnBrowser():
    palette = [
        ('blank', 'white', 'black'),
        ('body', 'white', 'black'),
        ('name', 'yellow', 'black'),
        ('string', 'light green', 'black'),
        ('foreign', 'light cyan', 'black'),
        ('type', 'dark gray', 'black'),
        ('focus', 'light gray', 'dark blue', 'standout'),
        ('head', 'yellow', 'black', 'standout'),
        ('foot', 'light gray', 'black'),
        ('key', 'light cyan', 'black','underline'),
        ('title', 'white', 'black', 'bold'),
        ('flag', 'dark gray', 'light gray'),
        ('error', 'dark red', 'light gray'),
    ]

    footer_text = [
        ('title', "Datamijn Data Browser"), "    ",
        ('key', "UP"), ",", ('key', "DOWN"), ",",
        ('key', "PAGE UP"), ",", ('key', "PAGE DOWN"),
        "  ",
        ('key', "+"), ",",
        ('key', "-"), "  ",
        ('key', "LEFT"), "  ",
        ('key', "HOME"), "  ",
        ('key', "END"), "  ",
        ('key', "Q"),
    ]

    def __init__(self, data=None):
        self.topnode = DatamijnBrowserParentNode(data)
        self.listbox = urwid.TreeListBox(urwid.TreeWalker(self.topnode))
        self.listbox.offset_rows = 1
        self.header = urwid.Text("")
        self.footer = urwid.AttrWrap(urwid.Text(self.footer_text),
            'foot')
        self.view = urwid.Frame(
            urwid.AttrWrap(self.listbox, 'body'),
            header=urwid.AttrWrap(self.header, 'head'),
            footer=self.footer)

    def main(self):
        self.screen = urwid.raw_display.Screen()
        self.screen.set_terminal_properties(256)
        self.loop = urwid.MainLoop(self.view, self.palette, screen=self.screen,
            unhandled_input=self.unhandled_input)
        self.loop.run()

    def unhandled_input(self, k):
        if k in ('q', 'Q'):
            raise urwid.ExitMainLoop()

