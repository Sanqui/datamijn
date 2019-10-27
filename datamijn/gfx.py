import os
from pathlib import Path
import array as pyarray

import png

from datamijn.dmtypes import Primitive, Array, ListArray
from datamijn.utils import bits

class Tile(Primitive):
    width = 8
    height = 8
    depth = 2
    
    @classmethod
    def size(self):
        return (self.depth*self.width*self.height)//8
    
    def __init__(self, tile):
        self.tile = tile
    
    def _open_with_path(self, ctx, path):
        output_dir = ctx[0]._output_dir
        filepath = "/".join(str(x) for x in path[:-1])
        filename = filepath + f"/{path[-1]}.png"
        full_filepath = output_dir + "/" + filepath
        full_filename = output_dir + "/" + filename
        os.makedirs(full_filepath, exist_ok=True)
        return filename.lstrip("/"), open(full_filename, 'wb')
    
    def __repr__(self):
        return f"<{type(self).__name__}>"

class PlanarTile(Tile):
    width = 8
    height = 8
    depth = 2
    invert = False
    
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        # assert self.width == 8
        tile_data = stream.read(self.depth*self.width*self.height//8)
        tile = pyarray.array("B", [0]*8*self.width)
        
        # 76543210
        # fedcba98
        # ->
        # ______80
        # ______91
        # ______a2 etc.
        
        i = 0
        for y in range(self.height):
            for d in range(self.depth):
                layer = tile_data[i] # bits(tile_data[i])
                i += 1
                #for x in range(8):
                # I promise this is faster
                tile[y*self.width + 7] |= (layer & 0b00000001)      << d
                tile[y*self.width + 6] |= (layer & 0b00000010) >> 1 << d
                tile[y*self.width + 5] |= (layer & 0b00000100) >> 2 << d
                tile[y*self.width + 4] |= (layer & 0b00001000) >> 3 << d
                tile[y*self.width + 3] |= (layer & 0b00010000) >> 4 << d
                tile[y*self.width + 2] |= (layer & 0b00100000) >> 5 << d
                tile[y*self.width + 1] |= (layer & 0b01000000) >> 6 << d
                tile[y*self.width    ] |= (layer & 0b10000000) >> 7 << d
            #if self.invert:
            #    line = [x ^ ((1 << self.depth) - 1) for x in line]
        return tile
    
    def _save(self, ctx, path):
        self._filename, f = self._open_with_path(ctx, path)
        w = png.Writer(self.width, self.height, greyscale=True, bitdepth=self.depth)
        w.write_array(f, self.tile)
        f.close()

class PlanarCompositeTile(PlanarTile):
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        #assert self.width == 8
        tile_data = stream.read(self.depth*self.width*self.height//8)
        tile = pyarray.array("B", [0]*8*self.width)
        i = 0
        for d in range(self.depth):
            for line in range(self.height):
                layer = bits(tile_data[i])
                i += 1
                for x in range(8):
                    tile[line*self.width + 7-x] |= layer[x] << d
        return tile
    
    def _save(self, ctx, path):
        self._filename, f = self._open_with_path(ctx, path)
        w = png.Writer(self.width, self.height, greyscale=True, bitdepth=self.depth)
        w.write_array(f, self.tile)
        f.close()

class Tile1BPP(PlanarTile):
    depth = 1

class NESTile(PlanarCompositeTile):
    depth = 2

class GBTile(PlanarTile):
    depth = 2
    invert = False


class Tileset(ListArray):
    def _save(self, ctx, path):
        palette = getattr(self, "_palette", None)
        if issubclass(self._child_type, Tile):
            # XXX maybe remove this
            for i, elem in enumerate(self):
                elem._save(ctx, path + [i])
            '''self._filename, f = self._type._open_with_path(self, ctx, path)
            width = 8
            height = len(self) * 8
            w = png.Writer(width, height,
                greyscale=True, bitdepth=self._type.depth)
            
            pic = pyarray.array("B", [])
            for y in range(height):
                for x in range(width):
                    tileno = ((y//8) * (width//8)) + x//8
                    if tileno < len(self):
                        pic.append(self[tileno].tile[(y%8) * 8 + x%8])
                    else:
                        pic.append(0)
            w.write_array(f, pic)
            f.close()'''
        elif issubclass(self._child_type, Tileset):
            self._filename, f = self._child_type._child_type._open_with_path(self, ctx, path)
            width = self._child_type._child_type.width*len(self[0])
            height = self._child_type._child_type.height*len(self)
            if not palette:
                w = png.Writer(width, height,
                    greyscale=True, bitdepth=self._child_type._child_type.depth)
            else:
                #assert self._type._type.depth <= 8
                # speed up rendering by using an 8-bit paletted png
                p8bit = palette.eightbit()
                palette = p8bit + [(0, 0, 0)] * (256-len(p8bit))
                w = png.Writer(width, height,
                    greyscale=False, palette=p8bit, bitdepth=8) # self._type._type.depth
            
            pic = pyarray.array("B", [])
            for y in range(height):
                for tilex in range(width//8):
                    pic.extend(self[y//8][tilex].tile[(y%8) * 8 :(y%8) * 8 + 8])
            w.write_array(f, pic)
            f.close()
        else:
            raise NotImplementedError()
    
    @classmethod
    def _or_type(self, other):
        if issubclass(other, Palette):
            return Image
        else:
            return None
    
    def __or__(self, other):
        if isinstance(other, Palette):
            image = Image(self)
            image._child_type = self._child_type
            image._palette = other
            return image
        else:
            return NotImplemented
    
    def __repr__(self):
        return f"<{type(self).__name__}>"
    
    def _pretty_repr(self):
        return repr(self)

class Image(Tileset):
    pass

class Palette(ListArray):
    def eightbit(self):
        # primitive reify
        if hasattr(self, "_eightbit"):
            return self._eightbit
        
        colors = []
        for color in self:
            mul = (255/color.max)
            colors.append((int(color.r * mul), int(color.g * mul), int(color.b * mul)))
        
        self._eightbit = colors
        
        return colors
    
    def __repr__(self):
        return f"<{type(self).__name__}>"

class Color(Primitive):
    @property
    def hex(self):
        raise NotImplementedError()

class RGBColor(Color):
    _inherited_fields = "r g b max".split()
    @property
    def hex(self):
        mul = (255/self.max)
        return "#{:02x}{:02x}{:02x}".format(int(self.r * mul), int(self.g * mul), int(self.b * mul))
    
    def __repr__(self):
        return f"RGBColor({self.r}, {self.g}, {self.b}, max={self.max})"

Array.ARRAY_CLASSES.update({
    (Tile,):            Tileset,
    (Tileset, Tile):    Tileset,
    (Color,):           Palette
})
