import adsk.core, adsk.fusion

from .dim import Dim, LENGTH, UNITLESS, ANGLE, literalExpression

BIN_PARAMETER_PREFIX = 'gfb'

class ParameterSpec:
    def __init__(self, key: str, kind: str, label: str, live: bool):
        self.key = key
        self.kind = kind
        self.label = label
        # live parameters drive the geometry, the rest are recorded for reference only
        self.live = live

# Order here is the order parameters appear in Change Parameters.
BIN_PARAMETER_SPECS = [
    ParameterSpec('bin_width_u', UNITLESS, 'bin width, X (u)', False),
    ParameterSpec('bin_length_u', UNITLESS, 'bin length, Y (u)', False),
    ParameterSpec('bin_height_u', UNITLESS, 'bin height, Z (u)', True),
    ParameterSpec('base_width', LENGTH, 'base width unit', True),
    ParameterSpec('base_length', LENGTH, 'base length unit', True),
    ParameterSpec('height_unit', LENGTH, 'bin height unit', True),
    ParameterSpec('xy_clearance', LENGTH, 'bin xy clearance', True),
    ParameterSpec('wall_thickness', LENGTH, 'bin wall thickness', True),
    ParameterSpec('screw_diameter', LENGTH, 'screw hole diameter', True),
    ParameterSpec('magnet_diameter', LENGTH, 'magnet cutout diameter', True),
    ParameterSpec('magnet_depth', LENGTH, 'magnet cutout depth', True),
    ParameterSpec('scoop_radius', LENGTH, 'scoop max radius', True),
    ParameterSpec('tab_length_u', UNITLESS, 'label tab length (u)', True),
    ParameterSpec('tab_width', LENGTH, 'label tab width', True),
    ParameterSpec('tab_offset_u', UNITLESS, 'label tab offset (u)', True),
    ParameterSpec('tab_angle', ANGLE, 'label tab overhang angle', True),
    ParameterSpec('compartments_x', UNITLESS, 'compartment grid width', False),
    ParameterSpec('compartments_y', UNITLESS, 'compartment grid length', False),
    ParameterSpec('compartments_custom', UNITLESS, 'custom compartment grid (1 = custom, 0 = uniform)', False),
    ParameterSpec('bin_type', UNITLESS, 'bin type (0 = hollow, 1 = shelled, 2 = solid)', False),
    ParameterSpec('generate_body', UNITLESS, 'generate body (1/0)', False),
    ParameterSpec('generate_base', UNITLESS, 'generate base (1/0)', False),
    ParameterSpec('has_lip', UNITLESS, 'lip for stackability (1/0)', False),
    ParameterSpec('has_lip_notches', UNITLESS, 'lip notches (1/0)', False),
    ParameterSpec('has_scoop', UNITLESS, 'scoop (1/0)', False),
    ParameterSpec('has_tab', UNITLESS, 'label tab (1/0)', False),
    ParameterSpec('has_screw_holes', UNITLESS, 'screw holes (1/0)', False),
    ParameterSpec('has_magnets', UNITLESS, 'magnet sockets (1/0)', False),
    ParameterSpec('has_magnet_tabs', UNITLESS, 'magnet socket tabs (1/0)', False),
]

def allocatePrefix(design: adsk.fusion.Design, base: str = BIN_PARAMETER_PREFIX) -> str:
    """Smallest gfbN_ prefix not used by any existing user parameter."""
    names = [design.userParameters.item(i).name for i in range(design.userParameters.count)]
    index = 1
    while any(name.startswith(f'{base}{index}_') for name in names):
        index += 1
    return f'{base}{index}_'

def createBinParameters(design: adsk.fusion.Design, prefix: str, values: dict) -> dict:
    """Create (or update, if already present) one user parameter per spec.

    `values` maps spec key to a number in API units (cm for lengths, radians for angles) or a bool.
    Returns spec key -> Dim referencing the parameter.
    """
    userParameters = design.userParameters
    result = {}
    groupName = prefix.rstrip('_')
    for spec in BIN_PARAMETER_SPECS:
        value = values[spec.key]
        if isinstance(value, bool):
            value = 1 if value else 0
        name = prefix + spec.key
        expression = literalExpression(float(value), spec.kind)
        comment = f'Gridfinity bin {groupName}: {spec.label}' + ('' if spec.live else ' (info only, changing it has no effect)')
        parameter = userParameters.itemByName(name)
        if parameter is None:
            parameter = userParameters.add(name, adsk.core.ValueInput.createByString(expression), spec.kind, comment)
        else:
            parameter.expression = expression
            parameter.comment = comment
        result[spec.key] = Dim.named(name, parameter.value, spec.kind)
    return result
