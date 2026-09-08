"""Source-derived signatures, without importing or evaluating fixture code."""
import ast
import inspect


class InvalidPlan(ValueError):
    pass


def signatures(source):
    result = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        args = node.args
        positional = args.posonlyargs + args.args
        defaults_start = len(positional) - len(args.defaults)
        parameters = []
        for i, arg in enumerate(positional):
            kind = inspect.Parameter.POSITIONAL_ONLY if i < len(args.posonlyargs) else inspect.Parameter.POSITIONAL_OR_KEYWORD
            parameters.append(inspect.Parameter(arg.arg, kind,
                default=None if i >= defaults_start else inspect.Parameter.empty))
        if args.vararg:
            parameters.append(inspect.Parameter(args.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
        for arg, default in zip(args.kwonlyargs, args.kw_defaults):
            parameters.append(inspect.Parameter(arg.arg, inspect.Parameter.KEYWORD_ONLY,
                default=None if default is not None else inspect.Parameter.empty))
        if args.kwarg:
            parameters.append(inspect.Parameter(args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
        result[node.name] = inspect.Signature(parameters)
    return result


def callable_help(source):
    # AST text preserves actual defaults; signatures above use placeholders only
    # for binding. No function body or default expression is evaluated here.
    return [f"{n.name}({ast.unparse(n.args)})" for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef)]


def bind_calls(source, calls):
    available = signatures(source)
    for index, call in enumerate(calls):
        name = call['function']
        if name not in available:
            raise InvalidPlan(f"Call {index + 1}: use a function defined in the source, not an agent tool. Allowed: {', '.join(available)}")
        try:
            available[name].bind(*call.get('args', []), **call.get('kwargs', {}))
        except TypeError:
            raise InvalidPlan(f"Call {index + 1}: arguments do not bind. Signature: {name}{available[name]} (displayed defaults indicate optional parameters)") from None
