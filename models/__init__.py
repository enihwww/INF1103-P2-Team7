"""models package: `from models import X` still works for every class and setting."""
from .models import *  # noqa: F401,F403
from .models import __all__  # noqa: F401
