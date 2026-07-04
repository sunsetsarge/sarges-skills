"""Per-source adapters. Each module exposes search()/get_by_doi() style functions that
return (list_of_Paper_dicts_or_None, status_dict). None of these should ever raise to
their caller in resolve.py — they catch internally and report status."""
