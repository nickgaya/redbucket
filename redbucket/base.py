import sys
from collections import namedtuple

Zone = namedtuple('Zone', ('name', 'rate'))
Zone.__doc__ += ': Namespace for rate limiting state'
Zone.name.__doc__ = 'Unique identifier for this zone'
Zone.rate.__doc__ = 'Rate limit in requests per second'

if sys.version_info >= (3, 7):
    RateLimit = namedtuple('RateLimit', ('zone', 'burst', 'delay'),
                           defaults=(0, 0))
else:
    RateLimit = namedtuple('RateLimit', ('zone', 'burst', 'delay'))
    RateLimit.__new__.__defaults__ = (0, 0)

RateLimit.__doc__ += ': Rate limit for a given zone'
RateLimit.zone.__doc__ = 'Rate limiting zone'
RateLimit.burst.__doc__ = 'Maximum burst with no delay'
RateLimit.delay.__doc__ = 'Maximum burst with delay'
