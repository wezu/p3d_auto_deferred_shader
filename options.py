import sys
if sys.version_info >= (3, 0):
    import configparser
else:
    import ConfigParser as configparser
from panda3d.core import *


class Options():
    def __init__(self, config_file):
        self.preset, self.setup, self.shadows_size=self._read_graphics_config(config_file)

    def get(self):
        return {'filter_setup':self.preset, 'shading_setup':self.setup, 'shadows':self.shadows_size}

    def _encode_ini_value(self, var):
        var_type=type(var)
        if var_type is type(Vec4()) or var_type is type(Vec3()) or  var_type is type(Vec2()) or var_type is type([]):
            return ', '.join([str(i) for i in var])
        if  var_type is type({}):
            combined=''
            for name, value in var.items():
                combined+=name+' : '+self._encode_ini_value(value)+'\n'
            return combined[:-1]
        if  var_type is type(Texture()):
            return '/'.join(str(var.get_filename()).split('/')[-2:])
        return str(var)

    def _decode_ini_value(self, var):
        if type(var) is type([]):
            if len(var) == 2:
                return Vec2(*(float(i) for i in var))
            elif len(var) == 3:
                return Vec3(*(float(i) for i in var))
            elif len(var) == 4:
                return Vec4(*(float(i) for i in var))
        try:
            return int(var)
        except ValueError:
            try:
                return float(var)
            except ValueError:
                return var

    def write_graphics_config(self, preset, shadows, setup, config_file):
        cfg=configparser.ConfigParser()
        cfg.add_section('SHADOWS')
        cfg.set('SHADOWS', 'size', str(shadows))
        cfg.add_section('SETUP')
        for name, value in setup.items():
            cfg.set('SETUP', str(name), str(value))
        for i, item in enumerate(preset):
            cfg.add_section(str(i))
            for name, value in item.items():
                cfg.set(str(i), name, self._encode_ini_value(value))
        with open(config_file, 'w') as f:
            cfg.write(f)

    def _read_graphics_config(self, config_file):
        gfx_config = configparser.ConfigParser()
        try:
            gfx_config.read(config_file)
        except Exception as err:
            print('error reading config file', config_file)
            print(err)
            return None, None
        preset=[x for x in gfx_config.sections() if x  not in ('SETUP','SHADOWS')]
        setup={}
        shadows_size=256
        for section in gfx_config.sections():
            section_dict={}
            for option in gfx_config.options(section):
                if option in  ('inputs', 'translate_tex_name', 'define'):
                    inputs={}
                    for line in gfx_config.get(section, option).split('\n'):
                        if line:
                            item=line.split(':')
                            key=item[0].strip()
                            value=item[1].split(',')
                            if len(value) == 1:
                                value=value[0].strip()
                            else:
                                value=[x.strip() for x in value]

                            inputs[key]=self._decode_ini_value(value)
                    section_dict[option]=inputs
                else:
                    section_dict[option]=self._decode_ini_value(gfx_config.get(section, option))
            if section == 'SETUP':
                setup={key.upper():value for key, value in section_dict.items()}
            elif section == 'SHADOWS':
                shadows_size=section_dict['size']
            else:
                preset[int(section)]=section_dict
        return preset, setup, shadows_size

