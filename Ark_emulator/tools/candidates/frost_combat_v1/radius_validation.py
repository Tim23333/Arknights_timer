def validate_radius_parameters(options):
    from .selection import validate_eligibility
    if (not isinstance(options,Mapping) or not {'radius','eligibility'} <= set(options)
        or set(options)-{'radius','eligibility','include_primary'}
        or type(options['radius']) not in (int,float) or not math.isfinite(options['radius']) or options['radius']<0):
        raise ValueError('qualified radius requires finite radius and explicit eligibility')
    if 'include_primary' in options and type(options['include_primary']) is not bool:
        raise ValueError('qualified radius include_primary requires strict bool')
    validate_eligibility(options['eligibility'],'qualified radius eligibility')
