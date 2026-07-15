"""carwatch — a tiny, deliberately noisy stand-in for a real computer-vision system.

It replays a "recording" (a JSON scenario) in accelerated real time and emits
sightings the way a production CV pipeline would: first guess early (POST),
corrections later (PUT), mistakes included. The test suite around it is the
point of this repo — see README.md.
"""

__version__ = "1.0.0"
