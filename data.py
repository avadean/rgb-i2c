from copy import deepcopy
from numpy import loadtxt, arctan2, inf, where, zeros
from time import time
from tqdm import tqdm
from display import Display, get_display_ID
from parameters import MODES, MODE_DEFAULT, \
                       PHASE_MODE_TICKS, \
                       COLOR_DEFAULT, COLOR_GRADIENT_DEFAULT, COLOR_METHODS, COLOR_METHOD_DEFAULT, \
                       ENERGY_METHODS, ENERGY_METHOD_DEFAULT, ENERGY_TICK_RATE_DEFAULT, \
                       EVENT_TIME_DIFFERENCE_TOLERANCE, GRADIENT_DELAY, GRADIENT_DELAY_PHASE, EXAMPLE_DATA, \
                       PI
from utility import get_color_from_gradient, get_num_ticks, get_quantity, get_rate, PhaseBin, get_phase_bin
import math


def preprocess_data(file_=None, mode=MODE_DEFAULT,displays=None,
                    energy_method=ENERGY_METHOD_DEFAULT,
                    normalise=True, mirror=False, out_file='example'):

    time_start = time()

    data = process_data(file_, displays, mode=mode, energy_method=energy_method, normalise=normalise, mirror=mirror)
    store_data(_file=out_file,data=data)

    time_end = time()

    print(f'Pre-processing complete in {time_end-time_start}s', )


def process_data(file_,
                 displays,
                 mode=MODE_DEFAULT,
                 color_method=COLOR_METHOD_DEFAULT,
                 energy_method=ENERGY_METHOD_DEFAULT,
                 energy_tick_rate=ENERGY_TICK_RATE_DEFAULT,
                 gradient_delay=GRADIENT_DELAY,
                 color_gradient=COLOR_GRADIENT_DEFAULT,
                 normalise=True,mirror=False):

    assert isinstance(file_, str)
    assert all(isinstance(display, Display) for display in displays)
    assert isinstance(color_method, str)
    assert isinstance(energy_tick_rate, (float, int))
    assert isinstance(gradient_delay, (float, int))
    assert isinstance(color_gradient, tuple)
    assert len(color_gradient) == 2
    assert all(isinstance(energy, (float, int)) and isinstance(color, int) for energy, color in zip(*color_gradient))
    assert isinstance(normalise, bool)  # Do we want to normalise the time of the data to have on avg. 100 data points per 5 sec?
    assert isinstance(mirror, bool)  # Do we want half the displays to "mirror" the other half? (Used when two composite displays are back-to-back)

    mode = mode.strip().lower()
    color_method = color_method.strip().lower()
    energy_method = energy_method.strip().lower()

    assert mode in MODES, f'{mode} is an unknown mode.'
    assert color_method in COLOR_METHODS, f'{color_method} is an unknown colour method.'
    assert energy_method in ENERGY_METHODS, f'{energy_method} is an unknown energy method.'

    data_raw = process_file(file_, mode=mode, normalise=normalise)  # The raw data from file.

    # Modes are just essentially a set of defined parameters.
    if mode == 'normal':

        # Do exactly what the user asked.
        pass

    elif mode == 'phase':

        # Tick the displayed data over time due to its energy.
        color_method = 'energy'
        energy_method = 'tick'

    elif mode == 'scatter':

        # Do what the user asked
        pass


    if mode == 'normal':

        # In normal mode, we simply show all the events and colour by the user defined parameters.
        # There is no work to do.

        pass

    elif mode == 'phase':

        # In phase mode, we require 2 sides to the layout, each of 2x2 displays.
        displays_dict = {0: [(display.X, display.Y) for display in displays if display.side == 0],
                         1: [(display.X, display.Y) for display in displays if display.side == 1]}

        assert (0, 0) in displays_dict[0]
        assert (0, 1) in displays_dict[0]
        assert (1, 0) in displays_dict[0]
        assert (1, 1) in displays_dict[0]
        assert (0, 0) in displays_dict[1]
        assert (0, 1) in displays_dict[1]
        assert (1, 0) in displays_dict[1]
        assert (1, 1) in displays_dict[1]

        # The process_file function has already ordered the data for us.
        # The first half of the data is for help with the phase diagram.
        # The second half of the data is to be display on side 1 as it would in 'normal' mode.

        data_phase = data_raw[:len(data_raw)//2]
        data_raw = data_raw[len(data_raw)//2:]

        # Let's go and process the data_raw as normal, and then tie in the phase data after.

    elif mode == 'scatter':

        # In scatter mode, we require 2 sides to the layout, each of 2x2 displays.
        displays_dict = {0: [(display.X, display.Y) for display in displays if display.side == 0],
                         1: [(display.X, display.Y) for display in displays if display.side == 1]}

        assert (0, 0) in displays_dict[0]
        assert (0, 1) in displays_dict[0]
        assert (1, 0) in displays_dict[0]
        assert (1, 1) in displays_dict[0]
        assert (0, 0) in displays_dict[1]
        assert (0, 1) in displays_dict[1]
        assert (1, 0) in displays_dict[1]
        assert (1, 1) in displays_dict[1]

        # The process_file function has already ordered the data for us.
        # The first half of the data is for help with the phase diagram.
        # The second half of the data is to be display on side 1 as it would in 'normal' mode.

        data_phase = data_raw[:len(data_raw)//2]
        data_raw = data_raw[len(data_raw)//2:]

        # Let's go and process the data_raw as normal, and then tie in the phase data after.

    if color_method == 'energy':  # Base the colouring on the energy of the detection.

        # Collect the list of DataPoints, accounting for the energy method.
        if energy_method == 'accumulate':
            data_processed = get_energy_accum_data(data_raw)
        elif energy_method == 'tick':
            data_processed = get_energy_tick_data(data_raw, gradient_delay=GRADIENT_DELAY_PHASE, phase_mode=mode=='phase')


    # Before creating the events, we need to tie in some phase data first.
    if mode == 'phase':
        # The data in data_raw comes in pairs, whereby we will display the phase of these pairs compared with the pairs in data_phase.
        # We create a bin of phase differences.
        # An exact arc will cut through 15 of the pixels on an 8x8 display. So we create 60 bins (one for each quadrant).

        phase_bins = []
        num_bins = 60

        for n in range(num_bins):
            lbound = 2.0 * PI * (float(n)) / float(num_bins)
            ubound = 2.0 * PI * (float(n+1)) / float(num_bins)

            phase_bins.append(PhaseBin(lbound, ubound))

        # This will store the 'data points' of pixel changes for the phase side.
        data_phase_processed = []

        # We store a count of how many bins are contributing to each pixel on the screen so we know whether to turn it off or not.
        # TODO: this assumes 2x2 lots of 8x8 screens.
        frame_counts = zeros((16, 16), dtype=int)

        for n in range(0, len(data_processed), 2):

            # (x, y) co-ordinates.
            A = (data_processed[n].x, data_processed[n].y)
            B = (data_processed[n+1].x, data_processed[n+1].y)
            C = (data_phase[n][2], data_phase[n][3])
            D = (data_phase[n+1][2], data_phase[n+1][3])

            phaseAB = float(arctan2(A[1]-B[1], A[0]-B[0], dtype=float))
            phaseCD = float(arctan2(C[1]-D[1], C[0]-D[0], dtype=float))

            # Get phase difference.
            #phase_diff = phaseAB - phaseCD
            # dot product
            #print("pos",A,B,C,D)
            #print("diff",A[0]-B[0],A[1]-B[1])
            phase_diff = float((A[0]-B[0])*(C[0]-D[0]))
            phase_diff = phase_diff/math.sqrt(float((A[0]-B[0])*(A[0]-B[0])+(A[1]-B[1])*(A[1]-B[1])))
            phase_diff = phase_diff/math.sqrt(float((C[0]-D[0])*(C[0]-D[0])+(C[1]-D[1])*(C[1]-D[1])))

            # Ensure angle is between 0 and 2PI.
            if phase_diff < 0.0:
                phase_diff += 2.0 * PI

            #### Ensures angle is between -PI and PI.
            ###if phase_diff > PI:
            ###    phase_diff -= 2.0 * PI

            ###if phase_diff <= -PI:
            ###    phase_diff += 2.0 * PI

            phase_bin = get_phase_bin(phase_bins, phase_diff)

            # Save a copy of what the frame looks like.
            frame_counts_old = deepcopy(frame_counts)

            # Turn that pixel off.
            frame_counts[phase_bin.y][phase_bin.x] -= 1

            # Increment this phase bin.
            phase_bin.count += 1

            # Work out which phase bin has the highest count at the moment.
            max_count = max([p.count for p in phase_bins])

            # Work out if the pixel displaying the x and y has changed.
            phase_bin.determine_x_y(max_count)

            # Turn the new pixel on.
            frame_counts[phase_bin.y][phase_bin.x] += 1

            # Has anything on the frame changed?
            frame_diff = frame_counts - frame_counts_old

            on_y, on_x = where(frame_diff > 0)
            off_y, off_x = where(frame_diff < 0)

            assert on_y.size == on_x.size == off_y.size == off_x.size, 'Error when creating phase diagram.'

            # If we have found a change, then create a data point for it if required.
            if on_y.size == 1:
                on_y, on_x = int(on_y), int(on_x)
                off_y, off_x = int(off_y), int(off_x)

                # Only turn the new pixel on, if the number of counts it had before was 0.
                if frame_counts_old[on_y][on_x] == 0:
                    data_phase_processed.append(DataPoint(on_x, on_y, side=0, energy=inf,
                                                          start_time=data_processed[n].start_time, gradient_delay=GRADIENT_DELAY_PHASE))

                # Only turn the old pixel off, if the number of counts it has now is 0.
                if frame_counts[off_y][off_x] == 0:
                    data_phase_processed.append(DataPoint(off_x, off_y, side=0, energy=-inf,
                                                          start_time=data_processed[n].start_time, gradient_delay=GRADIENT_DELAY_PHASE))

    # Before creating the events, we need to tie in some phase data first.
    if mode == 'scatter':
        # The data in data_raw comes in pairs, whereby we will display the phase of these pairs compared with the pairs in data_phase.
        # We create a bin of phase differences.
        # An exact arc will cut through 15 of the pixels on an 8x8 display. So we create 60 bins (one for each quadrant).

        phase_bins = []
        num_bins = 60

        for n in range(num_bins):
            lbound = 2.0 * PI * (float(n)) / float(num_bins)
            ubound = 2.0 * PI * (float(n+1)) / float(num_bins)

            phase_bins.append(PhaseBin(lbound, ubound))

        # This will store the 'data points' of pixel changes for the phase side.
        data_phase_processed = []

        # We store a count of how many bins are contributing to each pixel on the screen so we know whether to turn it off or not.
        # TODO: this assumes 2x2 lots of 8x8 screens.
        frame_counts = zeros((16, 16), dtype=int)

        for n in range(0, len(data_processed), 2):

            # (x, y) co-ordinates.
            A = (data_processed[n].x, data_processed[n].y)
            B = (data_processed[n+1].x, data_processed[n+1].y)
            C = (data_phase[n][2], data_phase[n][3])
            D = (data_phase[n+1][2], data_phase[n+1][3])

            phaseAB = float(arctan2(A[1]-B[1], A[0]-B[0], dtype=float))
            phaseCD = float(arctan2(C[1]-D[1], C[0]-D[0], dtype=float))

            # Get phase difference.
            #phase_diff = phaseAB - phaseCD
            # dot product
            #print("pos",A,B,C,D)
            #print("diff",A[0]-B[0],A[1]-B[1])
            phase_diff = float((A[0]-B[0])*(C[0]-D[0]))
            phase_diff = phase_diff/math.sqrt(float((A[0]-B[0])*(A[0]-B[0])+(A[1]-B[1])*(A[1]-B[1])))
            phase_diff = phase_diff/math.sqrt(float((C[0]-D[0])*(C[0]-D[0])+(C[1]-D[1])*(C[1]-D[1])))

            phase_bin = get_phase_bin(phase_bins, phase_diff)

            # Save a copy of what the frame looks like.
            frame_counts_old = deepcopy(frame_counts)

            # Turn that pixel off.
            frame_counts[phase_bin.y][phase_bin.x] -= 1

            # Increment this phase bin.
            phase_bin.count += 1

            # Work out which phase bin has the highest count at the moment.
            max_count = max([p.count for p in phase_bins])

            # Work out if the pixel displaying the x and y has changed.
            phase_bin.determine_x_y(max_count)

            # Turn the new pixel on.
            frame_counts[phase_bin.y][phase_bin.x] += 1

            # Has anything on the frame changed?
            frame_diff = frame_counts - frame_counts_old

            on_y, on_x = where(frame_diff > 0)
            off_y, off_x = where(frame_diff < 0)

            assert on_y.size == on_x.size == off_y.size == off_x.size, 'Error when creating phase diagram.'

            # If we have found a change, then create a data point for it if required.
            if on_y.size == 1:
                on_y, on_x = int(on_y), int(on_x)
                off_y, off_x = int(off_y), int(off_x)

                # Only turn the new pixel on, if the number of counts it had before was 0.
                if frame_counts_old[on_y][on_x] == 0:
                    data_phase_processed.append(DataPoint(on_x, on_y, side=0, energy=inf,
                                                          start_time=data_processed[n].start_time, gradient_delay=GRADIENT_DELAY_PHASE))

                # Only turn the old pixel off, if the number of counts it has now is 0.
                if frame_counts[off_y][off_x] == 0:
                    data_phase_processed.append(DataPoint(off_x, off_y, side=0, energy=-inf,
                                                          start_time=data_processed[n].start_time, gradient_delay=GRADIENT_DELAY_PHASE))
                    
    #print(" ")
    #print("Colour method is ",color_method)
    #print("Energy method is ",energy_method)
    #print(" ")
    #numEvent = 0
    #for event in data_processed:
    #    numEvent += 1
    #    print("Data item ",numEvent," details: x,y ",event.x,event.y," side ",event.side," energy details ",event.energy,event.energy_tick_rate,event.ticks,event.gradient_delay,event.start_time,event.end_time)
    
    if color_method == 'energy':  # Base the colouring on the energy of the detection.

        # Now turn the DataPoints into events, accounting for the energy method.
        if energy_method == 'accumulate':
            #print(color_gradient)
            color_gradient = ([300],
                              [0])
            print(color_gradient)
            events = get_energy_accum_events(data_processed, displays, color_gradient)
        elif energy_method == 'tick':
            events = get_energy_tick_events(data_processed, displays, color_gradient)

    if mode == 'phase':
        events_phase = get_energy_tick_events(data_phase_processed, displays, color_gradient)

        events += events_phase


    #print(" ")
    #numEvent = 0
    #for event in events:
    #    numEvent += 1
    #    print("Event ",numEvent)
    #    print("x_values    ",event.x_values)
    #    print("y_values    ",event.y_values)
    #    print("colors      ",event.colors)
    #    print("display_IDs ",event.display_IDs)
    #    print("start_time  ",event.start_time)
    #    print(" ")
    
    # Make sure the events are in time order.
    events = sorted(events)
    #print(" ")
    #numEvent = 0
    #for event in events:
    #    numEvent += 1
    #    print("Sorted Event ",numEvent)
    #    print("x_values    ",event.x_values)
    #    print("y_values    ",event.y_values)
    #    print("colors      ",event.colors)
    #    print("display_IDs ",event.display_IDs)
    #    print("start_time  ",event.start_time)
    #    print(" ")

    # All events at the moment are individual pixel updates.
    # Let's group multiple pixel updates together into a single event, IF they are very close together in time.
    events = group_events(events)

    # Let's construct the pixel map for one display
    rows, cols = (8, 8)

    for ID in range(4):
        # Create and initialise to zero
        pixelmap = [[0 for i in range(cols)] for j in range(rows)]

        for event in events:
            #print("Display IDs",event.display_IDs)
            #print("x",event.x_values)
            #print("y",event.y_values)
            for plot in range(len(event.x_values)):
                if (event.display_IDs[plot]==ID):
                    pixelmap[event.x_values[plot]][event.y_values[plot]]+=1

        print(" ")
        print("Pixel map for display ",ID)
        for j in range(rows):
            print(pixelmap[j])

            #print(" ")
    #numEvent = 0
    #for event in events:
    #    numEvent += 1
    #    print("Grouped Event ",numEvent)
    #    print("x_values    ",event.x_values)
    #    print("y_values    ",event.y_values)
    #    print("colors      ",event.colors)
    #    print("display_IDs ",event.display_IDs)
    #    print("start_time  ",event.start_time)
    #    print(" ")

    return events


def process_file(file_, mode=MODE_DEFAULT, normalise=False):
    assert isinstance(file_, str)
    assert isinstance(mode, str)
    assert isinstance(normalise, bool)  # Do we want to normalise the time data to have on avg. 100 data points per 5 sec?

    data = loadtxt(file_, delimiter=',')

    assert len(data.shape) == 2, 'Need more than 1 data point.'  # Dealing with numpy's awkward shape size.
    assert data.shape[0] > 0, f'No data in file {file_}.'
    assert data.shape[1] == 6, 'Number of columns of data should be 6.'

    # We need four pieces of data: the initial photon hits on each detector, and
    # the two hits from those photons scattering
    assert data.shape[0] % 4 == 0, 'We require 4 pieces of data for each event.'

    # Extract the time, crystal ID, detector side, x, y and energy from the data
    # as tuples
    time, ID, side, x, y, energy = zip(*data)

    # Convert the tuples to lists
    time = list(map(float, time))
    ID = list(map(int, ID))
    side = list(map(int, side))
    x = list(map(int, x))  # NB lowercase x refers to the pixel coordinate in (16,16)
    y = list(map(int, y))  # NB lowercase y refers to the pixel coordinate in (16,16)
    energy = list(map(float, energy))

    assert all(t >= 0.0 for t in time), 'Data point with time < 0.'
    assert all(s >= 0 for s in side), 'Data point with side < 0.'
    assert all(x_i >= 0 for x_i in x), 'Data point with x pixel < 0.'
    assert all(y_i >= 0 for y_i in y), 'Data point with y pixel < 0.'
    #assert all(e >= 0.0 for e in energy), 'Data point with energy < 0.'  # TODO: include?

    energy = [1.0 for e in energy]  # TODO: add mode for this.

    if normalise:
        minimum = min(time)
        difference = max(time) - minimum

        num_data_points = data.shape[0]
        factor = 5.0 * float(num_data_points) / 5000.0

        time = [factor * (t - minimum) / (difference) for t in time]

    return list(zip(time, ID, x, y, side, energy))  # Note: we have put side to the right of (x, y) rather than the left.


def group_events(events):
    ''' Group events together that occur within the EVENT_TIME_DIFFERENCE_TOLERANCE. '''

    assert all(isinstance(e, Event) for e in events)

    grouped_events = []

    n = 0  # Manual counter, so we can avoid already-processed events.

    while n < len(events):
        event = events[n]

        x_values = event.x_values
        y_values = event.y_values
        colors = event.colors
        display_IDs = event.display_IDs

        count = 0

        # Loop through events ahead of this.
        for future_event in events[n+1:]:

            # If the future event start time is very close to this event, get its data.
            if (future_event.start_time - event.start_time) < EVENT_TIME_DIFFERENCE_TOLERANCE:
                x_values += future_event.x_values
                y_values += future_event.y_values
                colors += future_event.colors
                display_IDs += future_event.display_IDs

                count += 1  # Record how many events we have processed.

            else:
                break  # We can stop looking as the events are ordered.

        grouped_events.append(Event(x_values, y_values, colors, display_IDs, event.start_time))

        n += count + 1  # `count` number of future events processed. +1 for `event` itself.

    return grouped_events


def get_energy_accum_data(data_raw):
    ''' Takes in the raw data, and returns the organised data points. This initially
        gets the data points with their own energy. It then ensures the data is sorted
        and the energies of the pixels updated to be accumulative. '''

    data_processed = []

    for t, ID, x, y, s, e in data_raw:  # time, crystal_ID, x, y, side, energy.
        data_processed.append(DataPoint(x, y, s, e, start_time=t))

    data_processed = sorted(data_processed)  # Sorted based on start_time.

    # We need to make the energy of the data point equal to itself plus the previous energy of the pixel.
    # If there are no hits of the pixel before data point, then its energy is left unchanged.
    #min_e = 0
    #max_e = 0
    for n, dA in enumerate(data_processed):  # d for data point.

        # We ignore the first data point as this will never need its energy updated.
        if n == 0:
            #min_e = dA.energy
            #max_e = dA.energy
            continue

        # Only bother look at data points before the currently considered one **in reverse**.
        for dB in data_processed[n-1::-1]:

            # We're looking for data points that hit the same pixel.
            if (dA.side == dB.side) and (dA.x == dB.x) and (dA.y == dB.y):

                # Both data points hit the same pixel. The energy of dA should be itself plus dB.
                dA.energy += dB.energy

                # Don't want to add any energies, as we would be double counting.
                break
        #if dA.energy < min_e:
        #    min_e = dA.energy
        #if dA.energy > max_e:
        #    max_e = dA.energy
    #kit=False
    #if kit:
    #    for n, dA in enumerate(data_processed):
    #        dA.energy -= min_e
    #    max_e -= min_e
    #    print(f"max energy = {max_e}")
    return data_processed


def get_energy_tick_data(data_raw, energy_tick_rate=ENERGY_TICK_RATE_DEFAULT, gradient_delay=GRADIENT_DELAY, phase_mode=False):
    ''' Takes in the raw data, and returns the organised data points. This initially
        gets the number of ticks and thus the alight-time of the data point. It then
        also carefully checks if any of the data points overlap in time and thus need
        to be merged.
        If in phase_mode, the energy tick rate required is set to enforce a constant
        number of ticks regardless the energy of the data point. '''

    data_processed = []

    for t, ID, x, y, s, e in data_raw:  # time, crystal_ID, x, y, side, energy.
        energy_tick_rate = get_rate(e, num_ticks=PHASE_MODE_TICKS) if phase_mode else energy_tick_rate  # Number of ticks held constant if in phase_mode.
        num_ticks = get_num_ticks(e, energy_tick_rate)  # *** Number of ticks this pixel has is based on the energy. ***
        alight_time = get_quantity(num_ticks, gradient_delay)  # How long should this pixel be lit up for?

        data_processed.append(DataPoint(x, y, s, e, energy_tick_rate, num_ticks, start_time=t, end_time=t+alight_time))

    data_processed = sorted(data_processed)  # Sorted based on start_time.

    if phase_mode:

        # We don't need to worry about overlapping data points when in phase mode as everything is shown sequentially.
        # We just need to set the start times of the data points accordingly.
        # Data: [A, B, C, D, E, F].
        # The pairs of data would be (A, B), (C, D), (E, F).
        # A should have start time of A.
        # B should have start time of A.
        # C should have start time of end time of A.
        # D should have start time of C.
        # E should have start time of end time of C.
        # F should have start time of E.
        # Etc...

        assert len(data_processed) % 2 == 0

        for n in range(0, len(data_processed), 2):

            # Don't need to update the start time of the initial data.
            if n != 0:
                time_diff = data_processed[n].start_time - data_processed[n-2].end_time

                data_processed[n].start_time -= time_diff
                data_processed[n].end_time -= time_diff  # We do end times too for completeness.

            time_diff = data_processed[n+1].start_time - data_processed[n].start_time

            data_processed[n+1].start_time -= time_diff
            data_processed[n+1].end_time -= time_diff  # We do end times too for completeness.

    else:

        # We need to make sure that any hits on pixels that are already lit up do not overwrite, but instead add, energy to the pixel.
        for n, dA in tqdm(enumerate(data_processed), desc="Processing tick data"):  # d for data point.

            # Only bother looking at data points ahead of the currently considered one.
            for dB in data_processed[n+1:]:
                # Data is sorted in time, so if event B starts after A has "ticked away" then no later events
                # need to be checked
                if (dB.start_time > dA.end_time):
                    break
                
                # We're looking for data points that hit the same pixel and iB starts before the end of iA.
                if (dA.side == dB.side) and (dA.x == dB.x) and (dA.y == dB.y):

                    # An event, dB, occurs within the time frame that dA is still alight.

                    # Therefore, we erase the ticks of the initial iA event that would occur after iB has started.
                    # This includes remove the final background colour tick of iA, which iB will now deal with.
                    dA.ticks -= get_num_ticks(dA.end_time-dB.start_time, gradient_delay)

                    # The initial iA event end time is now equal to the latter iB event start time.
                    dA.end_time = dB.start_time

                    # The energy of the latter iB event will be itself plus |the energy of the initial iA event minus the amount it has decayed by|.
                    dB.energy += dA.energy - dA.ticks * energy_tick_rate

                    # Now re-compute the (greater) number of ticks and the (later) end time for the latter iB event.
                    dB.ticks = get_num_ticks(dB.energy, energy_tick_rate)  # *** Number of ticks this pixel has is based on the energy. ***
                    dB.end_time = dB.start_time + get_quantity(dB.ticks, gradient_delay)  # Start time + alight time.

                    # If dA overlaps with a dC, this will be dealt with by dB, so may as well break here to save time.
                    break

    return data_processed


def get_energy_accum_events(data_points, displays, color_gradient=COLOR_GRADIENT_DEFAULT):
    ''' get_energy_accum_data should be used before this to obtain the data_points. '''
    ''' This takes a DataPoint and creates the associated events based on the energy,
        given the energy_method is accumulate. This is just one event per data point. '''

    events = []
    for data_point in data_points:
        color = COLOR_DEFAULT if data_point.energy <= 0.0 else get_color_from_gradient(data_point.energy, color_gradient,len(data_points))

        display_ID = get_display_ID(displays, data_point.x, data_point.y, data_point.side)

        x = data_point.x % displays[display_ID].size  # Turns global x into local.
        y = data_point.y % displays[display_ID].size  # Turns global y into local.

        events.append(Event([x], [y], [color], [display_ID], data_point.start_time))  # x, y, color, ID are lists.

    # Add an extra event at the end so the display doesn't vanish immediately.
    if len(events) > 0:
        e = events[-1]
        events.append(Event(e.x_values, e.y_values, e.colors, e.display_IDs, e.start_time+1.0))  # 1 second later.

    return events


def get_energy_tick_events(data_points, displays, color_gradient=COLOR_GRADIENT_DEFAULT):
    ''' get_energy_tick_data should be used before this to obtain the data_points. '''
    ''' This takes a DataPoint and creates the associated events based on the energy, given the energy_method
        is ticks. For example, if a data point is a pixel light-up with 13eV, then if the energy_tick_rate is
        5eV, then the events will be a 13eV colour, 8eV colour `gradient_delay` seconds later, 3 eV colour
        `gradient_delay` seconds later, 0 eV (blank) colour `gradient_delay` seconds later. '''

    events = []
    print("Total points ",len(data_points))
    d = 0
    for data_point in tqdm(data_points, desc="Processing tick events"):
        #if(d%4==0):
        #    print(" ")
        d += 1
        for tick in range(data_point.ticks+1):
            #print("Tick ",tick)
            energy = data_point.energy - tick * data_point.energy_tick_rate

            color = COLOR_DEFAULT if energy <= 0.0 else get_color_from_gradient(energy, color_gradient,len(data_points))
            #print("Colour is ",color)

            display_ID, mirror_ID = get_display_ID(displays, data_point.x, data_point.y, data_point.side)

            #if (tick==0):
            #    print("Global coord data ",data_point.x, data_point.y, data_point.side)
            #print("Displays are ",display_ID,mirror_ID)
            # If this side or pixel don't map to a display, we ignore it
            if (display_ID>=0):
                x = data_point.x % displays[display_ID].size  # Turns global x into local.
                y = data_point.y % displays[display_ID].size  # Turns global y into local.
                #if (tick==0):
                #    print("Pixel data ",x,y, " on ",display_ID)
                events.append(Event([x], [y], [color], [display_ID], data_point.start_time+tick*data_point.gradient_delay))  # x, y, color, ID are lists.
            if (mirror_ID>=0):
                x = displays[mirror_ID].size - 1 - data_point.x % displays[mirror_ID].size  # Turns global x into local and *mirrors*
                y = data_point.y % displays[mirror_ID].size  # Turns global y into local.
                #if (tick==0):
                #    print("Pixel data ",x,y, " on ",mirror_ID)
                events.append(Event([x], [y], [color], [mirror_ID], data_point.start_time+tick*data_point.gradient_delay))  # x, y, color, ID are lists.
    return events

def store_data(data, _file='example'):
    ''' Function to store preprocessed event data in a file for displaying later'''
    import pickle

    print(f"Dumping processed data to file: {_file}" )
    # Dump data to file
    dbfile = open(_file, 'ab')
    # source, destination
    pickle.dump(data, dbfile)
    dbfile.close()
    print('Done')
    return

def load_data(_file='example'):
    ''' Function to load preprocessed event data from file for displaying.'''
    import pickle
    print(f"Loading processed data from file: {_file}" )
    dbfile = open(_file, 'rb')
    data = pickle.load(dbfile)
    dbfile.close()
    print('Done')
    return data

class DataPoint:
    def __init__(self, x, y, side=0, energy=0.0, energy_tick_rate=ENERGY_TICK_RATE_DEFAULT,
                 ticks=0, gradient_delay=GRADIENT_DELAY, start_time=0.0, end_time=inf):
        assert isinstance(x, int)
        assert isinstance(y, int)
        assert isinstance(side, int)
        assert isinstance(energy, (float, int))
        assert isinstance(energy_tick_rate, (float, int))
        assert isinstance(ticks, int)
        assert isinstance(gradient_delay, (float, int))
        assert isinstance(start_time, (float, int))
        assert isinstance(end_time, (float, int))

        self.x = x  # This is the global x co-ordinate.
        self.y = y  # This is the global y co-ordinate.
        self.side = side
        self.energy = energy
        self.energy_tick_rate = energy_tick_rate
        self.ticks = ticks  # With the given energy, how many `GRADIENT_DELAY` ticks will occur until the pixel is DEFAULT_COLOR again?
        self.gradient_delay = gradient_delay
        self.start_time = start_time
        self.end_time = end_time

    def __lt__(self, other):
        return self.start_time < other.start_time

    def __repr__(self):
        return f'({self.x},{self.y})  {self.energy:6.2f}  {self.start_time:6.2f}'


class Event:
    def __init__(self, x_values, y_values, colors, display_IDs, start_time=0.0):
        assert all(isinstance(x, int) for x in x_values)
        assert all(isinstance(y, int) for y in y_values)
        assert all(isinstance(color, int) for color in colors)
        assert all(isinstance(ID, int) for ID in display_IDs)
        assert all(255 >= color >= 0 for color in colors)
        assert isinstance(start_time, (float, int))

        self.x_values = x_values  # These are the local x co-ordinates.
        self.y_values = y_values  # These are the local y co-ordinates.
        self.colors = colors
        self.display_IDs = display_IDs
        self.start_time = start_time

    def __iter__(self):
        return iter(zip(self.x_values, self.y_values, self.colors, self.display_IDs))

    def __lt__(self, other):
        return self.start_time < other.start_time

    def __repr__(self):
        s = ''

        for x, y, color, display_ID in self:
            s += f'({x},{y})  {color}  {self.start_time:6.2f}\n'

        return s[:-1]

