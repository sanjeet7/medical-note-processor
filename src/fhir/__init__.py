"""
FHIR Conversion Module

Converts structured medical data from Part 4 agent extraction into
FHIR R4 compliant resources using the fhir.resources library.

Components:
- mappers: Individual resource mappers (Patient, Condition, etc.)
- bundler: FHIR Bundle creator
- converter: Main conversion service
"""
from .converter import FHIRConverter
from .bundler import FHIRBundler

__all__ = [
    "FHIRConverter",
    "FHIRBundler",
]
