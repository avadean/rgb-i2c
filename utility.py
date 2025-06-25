from numpy import ceil
from time import sleep

from parameters import WAIT_INITIAL


def wait_for_matrix_ready():
    sleep(WAIT_INITIAL)


def int_to_bytes(num):
    assert isinstance(num, int)

    assert num <= 65535, f'{num} too big, should be <= 65535'
    assert num >= 0, f'{num} too small, should be >= 0'

    return [int(i) for i in num.to_bytes(2, byteorder='big', signed=True)]


def get_color_from_gradient(quantity, color_gradient, total_points=100):
    ''' This returns the colour associated with a given quantity and colour gradient pattern.
        For example, the quantity could be an energy. For high energies it could return white
        and for low return blue. '''

    assert isinstance(quantity, (float, int))
    assert isinstance(total_points, int)

    bounds, colors = color_gradient

    # Assume that each point is two photons, so "total_points" is twice as large as we want for color scale
    # we convert to a percentage of the actual events
    scaled_quantity = 100*quantity/(total_points/2)
    
    max_c = 0
    # step = bounds[0]-bounds[1]
    # Loop through the bounds from smallest to largest.
    for upper_bound, color in zip(bounds[::-1], colors[::-1]):

        if scaled_quantity <= upper_bound:

            return color

    return max_c  # If we the quantity doesn't fit anywhere, assume it is the highest quantity colour.


def get_num_ticks(quantity, rate):
    ''' Gets the number of ticks needed to take a quantity down to 0.
        E.g if we have 18eV and a tick rate of 5eV, then it will take
        4 ticks to reduce this to 0eV. '''

    return int(ceil(quantity / rate))


def get_rate(quantity, num_ticks):
    ''' Get the rate that a quantity should change based on the number
        of ticks required. E.g if we have 18eV and 2 ticks, then the
        rate should be 9eV per tick. '''

    return quantity / float(num_ticks)


def get_quantity(num_ticks, rate):
    ''' Similar to above. This quantity could be, for example, the
        amount of time where the rate is the time delay. Or, the
        amount of energy where the rate is the energy decay. '''
    return float(num_ticks) * rate
