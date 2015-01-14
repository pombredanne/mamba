import operator
from interpreter.exceptions import *
import interpreter.symbol_table

symbols = interpreter.symbol_table.SymbolTable()


class InstructionList:
    def __init__(self, children=None):
        if children is None:
            children = []
        self.children = children

    def __iter__(self):
        return iter(self.children)

    def __repr__(self):
        return '<Instruction list: {0}>'.format(self.children)

    def eval(self):
        '''
        Evaluates all the class children and returns the result
        of their eval method in a list or returns an ExitStatement
        in case one is found
        '''

        ret = []
        for n in self:
            if isinstance(n, ExitStatement):
                return n

            res = n.eval()

            if isinstance(res, ExitStatement):
                return res
            elif res is not None:
                ret.append(res)

        return ret


class BaseExpression:
    def eval(self):
        raise NotImplementedError()


class ExitStatement(BaseExpression):
    def __iter__(self):
        return []

    def eval(self):
        pass


class ReturnStatement(ExitStatement):
    def __init__(self, expr: BaseExpression):
        self.expr = expr

    def __repr__(self):
        return '<Return expr={0}>'.format(self.expr)

    def eval(self):
        return full_eval(self.expr)


def full_eval(expr: BaseExpression):
    '''
    Fully evaluates the passex expression returning it's value
    '''

    while isinstance(expr, BaseExpression):
        expr = expr.eval()

    return expr


class Primitive(BaseExpression):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return '<Primitive: "{0}"({1})>'.format(self.value, self.value.__class__)

    def eval(self):
        return self.value


class Array(BaseExpression):
    def __init__(self, values: InstructionList):
        self.values = values

    def __repr__(self):
        return '<Array len: {0} [{1}]>'.format(len(self.values.children), self.values)

    def eval(self):
        return self.values.eval()


class ArrayAccess(BaseExpression):
    def __init__(self, array: Identifier, index: BaseExpression):
        self.array = array
        self.index = index

    def eval(self):
        return self.array.eval()[self.index.eval()]


class ArrayAssign(BaseExpression):
    def __init__(self, array: Identifier, index: BaseExpression, value: BaseExpression):
        self.array = array
        self.index = index
        self.value = value

    def eval(self):
        self.array.eval()[self.index.eval()] = self.value.eval()


class Identifier(BaseExpression):
    is_function = False

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Identifier: {0}>'.format(self.name)

    def assign(self, val):
        if self.is_function:
            symbols.setfunc(self.name, val)
        else:
            symbols.setsym(self.name, val)

    def eval(self):
        if self.is_function:
            return symbols.getfunc(self.name)

        return symbols.getsym(self.name)


class Assignment(BaseExpression):
    def __init__(self, identifier: Identifier, val):
        self.identifier = identifier
        self.val = val

    def __repr__(self):
        return '<Assignment: sym = {0}; val = {1}>'.format(self.identifier, self.val)

    def eval(self):
        if self.identifier.is_function:
            self.identifier.assign(self.val)
        else:
            self.identifier.assign(self.val.eval())


class BinaryOperation(BaseExpression):
    __operations = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '**': operator.pow,
        '/': operator.truediv,
        '%': operator.mod,

        '>': operator.gt,
        '>=': operator.ge,
        '<': operator.lt,
        '<=': operator.le,
        '==': operator.eq,
        '!=': operator.ne,

        'and': operator.and_,
        'or': operator.or_,
    }

    def __repr__(self):
        return '<Binary operation: left = {0}; right = {1}>'.format(self.left, self.right)

    def __init__(self, left, right, op):
        self.left = left
        self.right = right
        self.op = op

    def eval(self):
        left = self.left.eval()
        right = self.right.eval()

        try:
            return self.__operations[self.op](left, right)
        except TypeError:
            fmt = (left.__class__.__name__, left, self.op, right.__class__.__name__, right)
            raise InterpreterRuntimeError("Unable to apply operation (%s: %s) %s (%s: %s)" % fmt)


class CompoundOperation(BaseExpression):
    __operations = {
        '+=': operator.iadd,
        '-=': operator.isub,
        '/=': operator.itruediv,
        '*=': operator.imul,
        '%=': operator.imod,
        '**=': operator.ipow,
    }

    def __init__(self, identifier: Identifier, modifier: BaseExpression, operation: str):
        self.identifier = identifier
        self.modifier = modifier
        self.operation = operation

    def eval(self):
        # Express the compound operation as a 'simplified' binary op
        # does not return anything as compound operations
        # are statements and not expressions

        l = self.identifier.eval()
        r = self.modifier.eval()

        try:
            self.identifier.assign(self.__operations[self.operation](l, r))
        except TypeError:
            fmt = (l.__class__.__name__, l, self.operation, r.__class__.__name__, r)
            raise InterpreterRuntimeError("Unable to apply operation (%s: %s) %s (%s: %s)" % fmt)


class UnaryOperation(BaseExpression):
    __operations = {
        '+': operator.pos,
        '-': operator.neg,
        'not': operator.not_
    }

    def __repr__(self):
        return '<Unary operation: operation={0} expr={1}>'.format(self.operation, self.expr)

    def __init__(self, operation, expr: BaseExpression):
        self.operation = operation
        self.expr = expr

    def eval(self):
        return self.__operations[self.operation](self.expr.eval())


class If(BaseExpression):
    def __init__(self, condition: BaseExpression, truepart: InstructionList, elsepart=None):
        self.condition = condition
        self.truepart = truepart
        self.elsepart = elsepart

    def __repr__(self):
        return '<If condition={0}; then={1}>'.format(self.condition, self.truepart)

    def eval(self):
        if self.condition.eval():
            return self.truepart.eval()
        elif self.elsepart is not None:
            if isinstance(self.elsepart, BaseExpression):
                return self.elsepart.eval()
            else:
                return self.elsepart.eval()


class For(BaseExpression):
    def __init__(self, variable: Identifier, start: Primitive, end: Primitive, asc: bool, body: InstructionList):
        self.variable = variable
        self.start = start
        self.end = end
        self.asc = asc  # ascending order
        self.body = body

    def __repr__(self):
        return '<For {0} {1} {2} >'.format(self.start, '->' if self.asc else '<-', self.end)

    def eval(self):
        for i in range(self.start.eval(), 1 + self.end.eval(), 1 if self.asc else -1):
            self.variable.assign(i)

            # in case of exit statement prematurely break the loop
            if isinstance(self.body.eval(), ExitStatement):
                break


class While(BaseExpression):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

    def __repr__(self):
        return '<While cond={0} body={1}>'.format(self.condition, self.body)

    def eval(self):
        while self.condition.eval():
            if isinstance(self.body.eval(), ExitStatement):
                break


class PrintStatement(BaseExpression):
    def __init__(self, items: InstructionList):
        self.items = items

    def __repr__(self):
        return '<Print: {0}>'.format(self.items)

    def eval(self):
        print(*self.items.eval(), end='', sep='')


class FunctionCall(BaseExpression):
    def __init__(self, name: Identifier, params: InstructionList):
        self.name = name
        self.params = params

    def __repr__(self):
        return '<Function call name={0} params={1}>'.format(self.name, self.params)

    def __eval_builtin_func(self):
        func = self.name.eval()
        args = []

        for p in self.params:
            args.append(full_eval(p))

        return func.eval(args)

    def __eval_udf(self):
        func = self.name.eval()
        args = {}

        # pair the defined parameters in the function signature with
        # whatever is being passed on.
        #
        # On the parameters we only need the name rather than fully evaluating them
        for p, v in zip(func.params, self.params):
            args[p.name] = full_eval(v)

        return func.eval(args)

    def eval(self):
        if isinstance(self.name.eval(), BuiltInFunction):
            return self.__eval_builtin_func()

        return self.__eval_udf()


class Function(BaseExpression):
    def __init__(self, params: InstructionList, body: InstructionList):
        self.params = params
        self.body = body

    def __repr__(self):
        return '<Function params={0} body={1}>'.format(self.params, self.body)

    def eval(self, args):
        symbols.set_local(True)

        for k, v in args.items():
            symbols.setsym(k, v)

        try:
            ret = self.body.eval()

            if isinstance(ret, ReturnStatement):
                return ret.eval()
        finally:
            symbols.set_local(False)

        return None


class BuiltInFunction(BaseExpression):
    def __init__(self, func):
        self.func = func

    def __repr__(self):
        return '<Builtin function {0}>'.format(self.func)

    def eval(self, args):
        return self.func(*args)