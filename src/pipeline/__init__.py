"""
ETL pipeline package.

Modules:
  extractor  — reads the MASTER sheet from .xlsm files into raw data structures
  validator  — validates extracted data against business rules
  pipeline   — Pipeline class orchestrating extract → validate → transform → load
"""
