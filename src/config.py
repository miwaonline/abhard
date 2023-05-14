import pathlib # to get current path
import yaml

# This code is needed to get the config right on the module import
path = pathlib.Path(__file__).parent.absolute().parent
cfg = f'{path}/etc/abhard.yml'

with open(cfg, 'r') as configfile:
    full = yaml.full_load(configfile)

def loadcfg():
    '''
This is an example how to analyse config just to have it stored somewhere
'''
    for key in full:
        cherrypy.log(f'{key} => {full[key]}')
        if key == 'rro':
            for rrotype in full[key]:
                cherrypy.log(rrotype)
                for device in full[key][rrotype]:
                    cherrypy.log(device['name'])

def fancyloadcfg():
    '''
And here is some crazy python stuff that checks all the rro/textfile items, searches
for the name there that matches myvar and returns either corresponding dict or None
if nothing was found :exploding_head:
'''
    dev = next((item for item in config.full['rro']['textfile'] if item['name'] == myvar), None)