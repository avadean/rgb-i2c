from display import display_rainbow_2, get_displays, switch_displays, switch_displays_from_chars, display_arranger, set_global_orientation,display_rainbow
from manager import run, preprocess_data
from smbus import SMBus
from time import sleep
import sys
#file_ = 'Imaging_data/QECos2DeltaPhi_0_180_true.dat'  # Data file.
#file_ = 'Imaging_data/QECos2DeltaPhi_72_92_true.dat'  # Data file.
#file_ = 'Imaging_data/test.dat'  # Data file.
#file_ = 'Imaging_data/tiny.dat'  # Data file.
#file_ = 'Imaging_data/super_tiny.dat'
#file_ = 'Imaging_data/tiny_morphed.dat'
file_ = 'Imaging_data/big_demo.dat'
file2_ = 'Processed_data/big_demo'
#layout = (4, 4)
layout = (4, 4, 4, 4, 4, 4)
#layout = 4
#layout = (1)
run_test=False
bus = SMBus(1)
displays = get_displays(bus, layout=layout, mirror=True)
print("num displays found", len(displays))
#print(len(displays))
#for display in displays:
#    print(display.addr)
set_global_orientation(bus,1)
#display_rainbow(bus,displays)
#sys.exit()

# Displays need to be organised.
# Use...
#print(display_arranger(bus, displays))#;exit()
# ... to see a graphic on how to arrange the displays.
#switch_displays_from_chars(displays, 'D', 'C')
#switch_displays_from_chars(displays, 'J', 'G')
#switch_displays_from_chars(displays, 'E', 'G')
#switch_displays_from_chars(displays, 'J', 'F')
if run_test:
    i=0
    while i<10:
        run(file_=file_, layout=layout, \
            bus=bus, displays=displays, \
            mode='normal', \
            energy_method='tick', \
            mirror=True,data_file=file2_)
        i+=1
else:
    preprocess_data(file_=file_,  mode='normal',displays=displays,
            energy_method='tick',
            normalise=True, mirror=True, out_file=file2_)

#run(file_=file_, layout=layout, \
#    bus=bus, displays=displays, \
#    mode='normal', \
#    energy_method='accumulate')

