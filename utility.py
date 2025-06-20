from numpy import ceil, cos, sin, isclose
from time import sleep

from parameters import GRADIENT_DELAY, WAIT_INITIAL, PI


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
    #print("Value ",quantity,scaled_quantity,total_points/2)
    
    max_c = 0
    # step = bounds[0]-bounds[1]
    # Loop through the bounds from smallest to largest.
    #print(" ")
    #print("Called with value ",quantity)
    for upper_bound, color in zip(bounds[::-1], colors[::-1]):
        #print("Value, testing upperbound ",quantity,scaled_quantity,upper_bound)
        if scaled_quantity <= upper_bound:
            #print(quantity)
            #print(253*quantity/bounds[0])
            
#            return int(220*quantity/bounds[0]) # - color
            #print("color ",color)
            return color
        #else:
        #print(quantity)
    return max_c #colors[0]  # If we the quantity doesn't fit anywhere, assume it is the highest quantity colour.


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


def get_phase_bin(bins, quantity):
    for b in bins:
        if quantity == b:
            return b

    # If we don't find a bin, try adding a bit of noise to ensure it is not due to numerical error.
    quantity -= 1.0E-9

    if quantity < 0.0:
        quantity += 2.0 * PI

    for b in bins:
        if quantity == b:
            return b

    # If the quantity is just on the edge, put it into that bin.
    ###max_bin = max(bins)

    ###if isclose(quantity, max_bin.ubound):
    ###    return max_bin

    ###min_bin = min(bins)

    ###if isclose(min_bin.lbound, quantity):
    ###    return min_bin

    raise ValueError(f'{quantity} does not fall into any of the bins provided.')


class PhaseBin:
    MATRIX_SIZE = 8  # TODO: assumes the displays are 8x8.

    def __init__(self, lbound, ubound):
        assert isinstance(lbound, (float, int))
        assert isinstance(ubound, (float, int))

        self.lbound = lbound
        self.ubound = ubound
        self.angle = (self.lbound + self.ubound) / 2.0

        self.count = 0

        self.determine_x_y(max_count=1)

    def __eq__(self, other):
        # Only implemented for floats/ints.
        assert isinstance(other, (float, int))

        return self.lbound < other <= self.ubound

    def __lt__(self, other):
        return self.lbound < other.lbound

    def __repr__(self):
        return f'{self.lbound:15.9f} -> {self.ubound:15.9f}'

    def determine_x_y(self, max_count):
        assert isinstance(max_count, (float, int))
        assert max_count >= self.count

        norm_radius = float(self.count) / float(max_count)

        self.x = int(ceil(norm_radius * self.MATRIX_SIZE * cos(self.angle)))
        self.y = int(ceil(norm_radius * self.MATRIX_SIZE * sin(self.angle)))

        # These transformations take us from the maths co-ordinate frame to the display co-ordinate frame.
        self.x += self.MATRIX_SIZE - 1
        self.y = self.MATRIX_SIZE - self.y

