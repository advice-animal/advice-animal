def advice_name_re(prefix: str) -> str:
    """
    returns a regular expression string that matches either prefix/ or prefix as the entire string.
    """
    return f"^({prefix}$|{prefix}/.*)$"
