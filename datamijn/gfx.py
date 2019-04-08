import os
from pathlib import Path
import array as pyarray

import png

from datamijn.dmtypes import Primitive, Array, ListArray, PipedPrimitive
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
        output_dir = getattr(ctx[0], "_output_dir", None)
        if not output_dir:
            output_dir = ctx[0]._filepath + "/datamijn_out/"
        output_dir = Path(output_dir)
        filepath = Path("/".join(str(x) for x in path[:-1]))
        filename = filepath / f"{path[-1]}.png"
        full_filepath = output_dir / filepath
        full_filename = output_dir / filename
        os.makedirs(full_filepath, exist_ok=True)
        return filename, open(full_filename, 'wb')

class PlanarTile(Tile):
    width = 8
    height = 8
    depth = 2
    invert = False
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        #assert self.width == 8
        tile_data = stream.read(self.depth*self.width*self.height//8)
        tile = pyarray.array("B", [0]*8*self.width)
        i = 0
        for y in range(self.height):
            for d in range(self.depth):
                layer = bits(tile_data[i])
                i += 1
                for x in range(8):
                    tile[y*self.width + 7-x] |= layer[x] << d
            #if self.invert:
            #    line = [x ^ ((1 << self.depth) - 1) for x in line]
        return self(tile)
    
    def _save(self, ctx, path):
        self._filename, f = self._open_with_path(ctx, path)
        w = png.Writer(self.width, self.height, greyscale=True, bitdepth=self.depth)
        w.write_array(f, self.tile)
        f.close()

class PlanarCompositeTile(PlanarTile):
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
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
        return self(tile)
    
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
        if issubclass(self._type, Tile):
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
        elif issubclass(self._type, Tileset):
            self._filename, f = self._type._type._open_with_path(self, ctx, path)
            width = self._type._type.width*len(self[0])
            height = self._type._type.height*len(self)
            if not palette:
                w = png.Writer(width, height,
                    greyscale=True, bitdepth=self._type._type.depth)
            else:
                w = png.Writer(width, height,
                    greyscale=False, palette=palette.eightbit(), bitdepth=self._type._type.depth)
            
            pic = pyarray.array("B", [])
            for y in range(height):
                for x in range(width):
                    pic.append(self[y//8][x//8].tile[(y%8) * 8 + x%8])
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
            image._type = self._type
            image._palette = other
            return image
        else:
            return NotImplemented
    
    def __repr__(self):
        return f"<{type(self).__name__}>"

class Image(Tileset):
    pass

class Palette(ListArray, PipedPrimitive):
    def eightbit(self):
        colors = []
        for color in self:
            mul = (255/color.max)
            colors.append((int(color.r * mul), int(color.g * mul), int(color.b * mul)))
        
        return colors
    
    def __repr__(self):
        return f"<{type(self).__name__}>"

class Color(PipedPrimitive):
    @property
    def hex(self):
        raise NotImplementedError()

class RGBColor(Color):
    def __init__(self, r, g, b, max):
        self.r = r
        self.g = g
        self.b = b
        self.max = max
    
    @classmethod
    def parse_left(self, container, ctx, path, index=None):
        return self(container.r, container.g, container.b, container._max)
    
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
