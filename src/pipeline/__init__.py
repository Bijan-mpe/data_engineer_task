"""
ETL pipeline package.

Modules:
  extractor  — reads the MASTER sheet from .xlsm files into raw data structures
  validator  — validates extracted data against business rules
  pipeline   — Pipeline class orchestrating extract → validate → transform → load

Public API
----------
  extract_file    — parse a .xlsm file into an ExtractedFile DTO
  ExtractionError — raised when a file cannot be parsed
"""

from src.pipeline.extractor import ExtractionError, extract_file

__all__ = ["extract_file", "ExtractionError"]
