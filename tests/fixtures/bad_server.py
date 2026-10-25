"""A server that writes a malformed frame, for adversarial tests."""

import sys

sys.stdout.write("this is not json\n")
sys.stdout.flush()
