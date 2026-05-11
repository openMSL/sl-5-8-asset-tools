"""LLM-based metadata enrichment for simulation assets.

Analyzes source asset files (.xodr, .xosc) and existing metadata to fill
empty fields using LLM reasoning. Uses SHACL vocabulary to constrain
outputs to valid values (inspired by ontology-based-nl-search patterns).

Can run as a standalone evaluation tool or as an optional pipeline step.
"""
