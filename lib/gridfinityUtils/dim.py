# Dimension values that carry a Fusion expression alongside their numeric value.
#
# Generators do their arithmetic on `Dim` objects exactly as they would on floats; the result
# remembers how it was computed (e.g. '(gfb1_bin_height_u - 1) * gfb1_height_unit') so features
# can be created with ValueInput.createByString(expr) and stay linked to user parameters.
# Plain floats keep working everywhere: toValueInput(float) falls back to createByReal.
#
# No adsk import at module level so this file can be unit tested outside Fusion.

import math

LENGTH = 'mm'
UNITLESS = ''
ANGLE = 'deg'


def _formatNumber(number: float) -> str:
    text = ('%.6f' % number).rstrip('0').rstrip('.')
    return '0' if text in ('', '-0') else text


def literalExpression(value: float, kind: str) -> str:
    """Expression for a plain number in API internal units (cm / unitless / rad)."""
    if kind == LENGTH:
        return f'{_formatNumber(value * 10)} mm'
    if kind == ANGLE:
        return f'{_formatNumber(math.degrees(value))} deg'
    return _formatNumber(value)


class Dim:
    def __init__(self, value: float, expr: str, kind: str = LENGTH, atomic: bool = True):
        self.value = float(value)
        self.expr = expr
        self.kind = kind
        # atomic expressions need no parentheses when used as an operand
        self.atomic = atomic
        # set on the result of unary minus so that -(-x) gives x back
        self.negationOf = None

    # constructors
    @staticmethod
    def mm(millimeters: float) -> 'Dim':
        return Dim(millimeters / 10, literalExpression(millimeters / 10, LENGTH), LENGTH)

    @staticmethod
    def cm(value: float) -> 'Dim':
        return Dim(value, literalExpression(value, LENGTH), LENGTH)

    @staticmethod
    def unitless(value: float) -> 'Dim':
        return Dim(value, literalExpression(value, UNITLESS), UNITLESS)

    @staticmethod
    def named(name: str, value: float, kind: str) -> 'Dim':
        """Reference to a user parameter called `name` whose current value (API units) is `value`."""
        return Dim(value, name, kind)

    # helpers
    def _operand(self) -> str:
        return self.expr if self.atomic else f'({self.expr})'

    @staticmethod
    def _coerce(other, kind: str) -> 'Dim':
        if isinstance(other, Dim):
            return other
        value = float(other)
        dim = Dim(value, literalExpression(value, kind), kind)
        dim.atomic = value >= 0
        return dim

    @staticmethod
    def _combineKinds(a: str, b: str, op: str) -> str:
        if op == '/' and a == b:
            return UNITLESS
        return a if a != UNITLESS else b

    def _binary(self, other, op: str, reverse: bool = False) -> 'Dim':
        # a plain number added to / subtracted from a Dim has the Dim's unit;
        # a plain number in a product / quotient is a unitless scale factor
        otherKind = self.kind if op in '+-' else UNITLESS
        if not isinstance(other, Dim):
            # identities keep expressions short: x + 0, x - 0, 0 + x, 0 - x, x * 1, 1 * x, x / 1
            number = float(other)
            if number == 0 and op in '+-':
                return -self if reverse and op == '-' else self
            if number == 1 and (op == '*' or (op == '/' and not reverse)):
                return self
            if number == 0 and (op == '*' or (op == '/' and reverse)):
                return 0.0
        other = Dim._coerce(other, otherKind)
        left, right = (other, self) if reverse else (self, other)
        if op == '+':
            value = left.value + right.value
        elif op == '-':
            value = left.value - right.value
        elif op == '*':
            value = left.value * right.value
        else:
            value = left.value / right.value
        kind = Dim._combineKinds(left.kind, right.kind, op)
        # left operand of + and - never needs parentheses; everything else does unless atomic
        leftOperand = left.expr if op in '+-' else left._operand()
        return Dim(value, f'{leftOperand} {op} {right._operand()}', kind, atomic=False)

    def __add__(self, other): return self._binary(other, '+')
    def __radd__(self, other): return self._binary(other, '+', reverse=True)
    def __sub__(self, other): return self._binary(other, '-')
    def __rsub__(self, other): return self._binary(other, '-', reverse=True)
    def __mul__(self, other): return self._binary(other, '*')
    def __rmul__(self, other): return self._binary(other, '*', reverse=True)
    def __truediv__(self, other): return self._binary(other, '/')
    def __rtruediv__(self, other): return self._binary(other, '/', reverse=True)

    def __neg__(self):
        if self.negationOf is not None:
            return self.negationOf
        negated = Dim(-self.value, f'-{self._operand()}', self.kind, atomic=False)
        negated.negationOf = self
        return negated

    def __abs__(self):
        return -self if self.value < 0 else self

    def __float__(self): return self.value
    def __lt__(self, other): return self.value < float(other)
    def __le__(self, other): return self.value <= float(other)
    def __gt__(self, other): return self.value > float(other)
    def __ge__(self, other): return self.value >= float(other)

    def __repr__(self):
        return f'Dim({self.value!r}, {self.expr!r}, {self.kind!r})'


def _function(name: str, pick, a, b):
    if not isinstance(a, Dim) and not isinstance(b, Dim):
        return pick(a, b)
    kind = a.kind if isinstance(a, Dim) else b.kind
    a = Dim._coerce(a, kind)
    b = Dim._coerce(b, kind)
    # Fusion expressions separate function arguments with semicolons
    return Dim(pick(a.value, b.value), f'{name}({a.expr}; {b.expr})', kind, atomic=True)


def dmax(a, b):
    """max() that keeps the expression when either argument is a Dim."""
    return _function('max', max, a, b)


def dmin(a, b):
    """min() that keeps the expression when either argument is a Dim."""
    return _function('min', min, a, b)


class DimPoint:
    """Point whose coordinates may be Dims. Use asPoint3D() where Fusion needs a Point3D."""
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def toPoint3D(self):
        import adsk.core
        return adsk.core.Point3D.create(float(self.x), float(self.y), float(self.z))

    def __repr__(self):
        return f'DimPoint({self.x!r}, {self.y!r}, {self.z!r})'


def isParametric(*values) -> bool:
    return any(isinstance(value, Dim) for value in values)


def asPoint3D(point):
    return point.toPoint3D() if isinstance(point, DimPoint) else point


def offsetPoint(point, byX=0, byY=0, byZ=0):
    """Point offset that returns a DimPoint when anything involved is parametric, else a Point3D."""
    x, y, z = point.x + byX, point.y + byY, point.z + byZ
    if isinstance(point, DimPoint) or isParametric(x, y, z):
        return DimPoint(x, y, z)
    import adsk.core
    return adsk.core.Point3D.create(x, y, z)


def toValueInput(value):
    import adsk.core
    if isinstance(value, Dim):
        return adsk.core.ValueInput.createByString(value.expr)
    return adsk.core.ValueInput.createByReal(float(value))


def applyExpression(sketchDimension, value):
    """Link a sketch dimension to `value`'s expression. Sketch dimensions are always positive,
    so a negative coordinate (point left of / below the sketch origin) is linked by its magnitude."""
    if isinstance(value, Dim):
        sketchDimension.parameter.expression = abs(value).expr
