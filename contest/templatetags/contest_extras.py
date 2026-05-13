from django import template


register = template.Library()


@register.filter
def country_flag(country_code):
    code = (country_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return code
    return "".join(chr(0x1F1E6 + ord(letter) - ord("A")) for letter in code)
