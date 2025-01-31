from data import COLORS


def create_pixels(colors):
    assert all(isinstance(i, int) for i in colors)

    assert all(255 >= i >= 0 for i in colors)

    return [Pixel(color) for color in colors]


class Pixel:
    color_default = COLORS['black']  # What colour should be set as the background?
    timer_default = 0.5  # How long is the default between gradient changes?

    def __init__(self, color=COLORS['black']):
        assert isinstance(color, int)

        assert 255 >= color >= 0, 'Colour number should be between 0 and 255.'

        self.color = color

        self.timer = None  # Current time remaining at the current colour. If None then no change unless later instructed.
        self.timers = None  # A generator holding the timers of a requested gradient pattern.
        self.gradient = None  # A generator holding the colours of a requested gradient pattern.

    def set_gradient(self, gradient, timers=None):
        assert all(isinstance(i, int) for i in gradient)

        if timers is not None:
            assert all(isinstance(i, (float, int)) for i in timers)
        else:
            timers = [self.timer_default] * len(gradient)

        assert len(timers) == len(gradient)
        assert len(timers) > 0

        assert all(i > 0.0 for i in timers)
        assert all(255 >= i >= 0 for i in gradient)

        self.timers = (i for i in timers)
        self.gradient = (i for i in gradient)

        self.timer = next(self.timers)
        self.color = next(self.gradient)

    def check_color_change(self, tick):
        assert isinstance(tick, (float, int))

        assert tick > 0.0, 'Tick should be > 0.0.'

        if self.timer is not None:  # Only check for a colour change if we have a timer going.
            self.timer -= tick  # Reduce the current colour timer by the tick.

            if self.timer <= 0.0:  # If this timer has ran out, then change the colour.

                try:
                    self.timer = next(self.timers)  # Get the timer for the next color.
                except StopIteration:
                    self.timer = None  # Reset back to None if we have reached the end of the gradient pattern.
                    self.timers = None

                try:
                    self.color = next(self.gradient)  # Get the next colour.
                except StopIteration:
                    self.color = self.color_default
                    self.gradient = None

