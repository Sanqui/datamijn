# Derived from the Urwid example for lazy directory browser / tree view
# See https://github.com/urwid/urwid/blob/master/examples/browse.py
import urwid
from datamijn.dmtypes import Container, Array, String, ForeignKey

class DatamijnBrowserTreeWidget(urwid.TreeWidget):
    def __init__(self, data):
        super().__init__(data)
        self._w = urwid.AttrMap(self._w, 'body', {'name': 'focus', 'body': 'focus', 'string': 'focus'})
        if isinstance(data, DatamijnBrowserParentNode):
            self.expanded = data._key is None
            self.update_expanded_icon()
    
    def load_inner_widget(self):
        node = self.get_node()
        value = node.get_value()
        
        name_color = 'name'
        body_color = 'body'
        
        if isinstance(node, DatamijnBrowserParentNode):
            valuetext = []
            if isinstance(value, ForeignKey):
                #name_color = 'name_foreign'
                body_color = 'name_foreign'
                valuetext += [(body_color, "→ ")]
                value = value._object
            if isinstance(value, String):
                valuetext += [("string", "\""+str(value)+"\"")]
            elif hasattr(value, 'name'):
                valuetext += [(body_color, str(value.name))]
            elif not isinstance(value, Container) and not isinstance(value, Array):
                valuetext += [(body_color, repr(value))]
        else:
            if isinstance(value, str):
                body_color = 'string'
            valuetext = [(body_color, repr(value))]
        
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
                return list(key for key in data.keys() if not key.startswith("_"))
            elif isinstance(data, Array):
                return range(len(data))
            elif isinstance(data, ForeignKey):
                return load_keys(data._object)
            else:
                return [None]
        data = self.get_value()
        return load_keys(data)

    def load_child_node(self, key):
        childdepth = self.get_depth() + 1
        if key == None:
            childdata = self.get_value()._object
            childclass = DatamijnBrowserNode
        else:
            childdata = self.get_value()[key]
            if isinstance(childdata, Container) or isinstance(childdata, Array) or isinstance(childdata, ForeignKey):
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
        ('name_foreign', 'light cyan', 'black'),
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
        self.loop = urwid.MainLoop(self.view, self.palette,
            unhandled_input=self.unhandled_input)
        self.loop.run()

    def unhandled_input(self, k):
        if k in ('q', 'Q'):
            raise urwid.ExitMainLoop()

