from display import display_rainbow_2, get_displays, switch_displays, switch_displays_from_chars, display_arranger, display_IDs,set_global_orientation,display_rainbow
from manager import run
from smbus import SMBus
from time import sleep

#file_ = 'Imaging_data/QECos2DeltaPhi_0_180_true.dat'  # Data file.
#file_ = 'Imaging_data/QECos2DeltaPhi_72_92_true.dat'  # Data file.
#file_ = 'Imaging_data/test.dat'  # Data file.
file_ = 'Imaging_data/tiny.dat'  # Data file.
#layout = (4, 4)
layout = 4
#layout = (1)
force_displays = False  # If we request more displays than addresses found, should we reuse displays anyway?

bus = SMBus(1)
displays = get_displays(bus, layout=layout,mirror=True)
print(len(displays))
for display in displays:
    print(display.addr)
set_global_orientation(bus,1)
display_rainbow(bus,displays)
sleep(1)
#displays[0].display_string(bus,"X",color=254,forever=True)
#input()

# If you want each display to show which bus ID it has
#display_IDs(bus)

# Displays need to be organised.
# Use...
#print(display_arranger(bus, displays))#;exit()
# ... to see a graphic on how to arrange the displays.
#switch_displays_from_chars(displays, 'D', 'C')
#switch_displays_from_chars(displays, 'J', 'G')
#switch_displays_from_chars(displays, 'E', 'G')
#switch_displays_from_chars(displays, 'J', 'F')

run(file_=file_, layout=layout, \
    bus=bus, displays=displays, \
    mode='normal', \
    energy_method='tick', \
    force_displays=force_displays, \
    mirror=True)

#run(file_=file_, layout=layout, \
#    bus=bus, displays=displays, \
#    mode='normal', \
#    energy_method='accumulate', \
#    force_displays=force_displays)

