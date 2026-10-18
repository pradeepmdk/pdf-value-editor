"""Solve an explicitly selected input for a desired, verified report result."""
from decimal import Decimal

from general_finance import parse_amount, format_amount, calculate
from statement_profiles import normalized, _order, evaluate, calculate_profile


def _rules(statement):
    return statement.get('profile_rules', statement.get('candidate_rules', []))


def _coefficients(target, rules):
    by_target = {r['target']: r for r in rules}
    def expand(key, active):
        if key not in by_target:
            return {key: Decimal(1)}
        if key in active or by_target[key].get('operation') == 'percentage':
            raise ValueError('Profit/loss needs a verified additive result formula.')
        result = {}
        for term in by_target[key]['terms']:
            for source, coefficient in expand(term['source'], active | {key}).items():
                result[source] = result.get(source, Decimal(0)) + coefficient * term['sign']
        return {key: value for key, value in result.items() if value}
    return expand(target, set())


def _definitions(statement):
    cells = statement['cells']
    rules = _rules(statement)
    if statement.get('export_mode') == 'direct' and rules:
        return [{'id': c['id'], 'label': c['column'], 'target': c['id'],
                 'coefficients': _coefficients(c['id'], rules)}
                for c in cells if c.get('row') == 'final']
    if statement.get('profile') == 'datev_cash_basis':
        return [{'id': c['id'], 'label': c['column'], 'target': c['id'],
                 'coefficients': _coefficients(c['id'], rules)}
                for c in cells if c['page'] == 1 and c.get('row') == normalized('Einnahmen-Ausgaben-BWA')
                and c.get('column_index') in (0, 4)]
    if statement.get('profile') == 'addison_susa':
        # This supported report uses SKR04 income/expense classes 4--7.
        # Validate the printed class and category anchors before exposing a goal.
        rows = {c.get('row') for c in cells}
        if not {'summeklasse4', 'summeklasse5', 'summeklasse6', 'summeklasse7',
                'umsatzerlose', 'summepersonalkosten'} <= rows:
            return []
        return [{'id': name, 'label': label, 'target': None,
                 'coefficients': {c['id']: Decimal(-1 if c['column_index'] == debit else 1)
                     for c in cells if str(c.get('row', '')).isdigit()
                     and 4000 <= int(c['row']) < 8000 and c.get('column_index') in (debit, credit)}}
                for name, label, debit, credit in [('susa_month', 'Month', 1, 2),
                                                  ('susa_ytd', 'Year to date', 3, 4)]]
    return []


def _input_coefficients(statement, definition, explicit=()):
    """Include monthly inputs whose delta propagates into year-to-date."""
    coefficients = dict(definition['coefficients'])
    for monthly, annual in statement.get('period_pairs', []):
        if annual not in explicit:
            coefficients[monthly] = coefficients.get(monthly, Decimal(0)) + definition['coefficients'].get(annual, Decimal(0))
    return {key: value for key, value in coefficients.items() if value}


REVENUE_ROWS = {'revenue', 'betrieblichertatigkeit', 'umsatzerlose', 'erlose'}


def _is_revenue(cell):
    row = str(cell.get('row', ''))
    return row in REVENUE_ROWS or (row.isdigit() and 4000 <= int(row) < 5000)


def _default_source(by_id, definition, sources):
    """Prefer the turnover printed in the result's own period column.

    A year-to-date target must change the yearly turnover, not December's,
    so the remaining amounts stay as printed.
    """
    target = by_id.get(definition['target']) if definition['target'] else None
    column = target.get('column_index') if target else max(
        (by_id[key].get('column_index', 0) for key in sources), default=0)
    same_column = [key for key in sources if by_id[key].get('column_index') == column]
    for group in (same_column, sources):
        revenue = [key for key in group if _is_revenue(by_id[key])]
        if revenue:
            return revenue[0]
    return (same_column or sources)[0]


def options(statement):
    by_id = {c['id']: c for c in statement['cells']}
    periods = []
    definitions = [] if statement.get('profile') and not statement.get('verified') else _definitions(statement)
    for definition in definitions:
        sources = [key for key, coefficient in _input_coefficients(statement, definition).items()
                   if coefficient in (Decimal(-1), Decimal(1)) and by_id[key].get('editable') is True]
        if not sources:
            continue
        default = _default_source(by_id, definition, sources)
        sources = [default] + [key for key in sources if key != default]
        target = definition['target']
        current = Decimal(by_id[target]['value']) if target else sum(
            (Decimal(by_id[key]['value']) * coefficient for key, coefficient in definition['coefficients'].items()), Decimal(0))
        periods.append({'id': definition['id'], 'label': definition['label'], 'target': target,
                        'current': format_amount(current, statement['locale']), 'sources': sources,
                        'default_source': default})
    return {'periods': periods, 'requires_counterpart': statement.get('profile') == 'addison_susa',
            'note': ('SuSa profit/loss is net credit minus debit movements in account classes 4–7. '
                     'Uses the selected income/expense input with a balance-sheet counterpart. No new result row is added to the PDF.'
                     if statement.get('profile') == 'addison_susa' else
                     'Enter the desired final result for the chosen period. Only the selected input is adjusted; verified totals recalculate.')}


def _values(statement, edits):
    """Apply explicit inputs and monthly propagation, then evaluate the formulas."""
    cells = {c['id']: c for c in statement['cells']}
    values = {key: Decimal(c['value']) for key, c in cells.items()}
    if not isinstance(edits, list) or len(edits) > 30 or any(not isinstance(e, dict) for e in edits):
        raise ValueError('Provide up to thirty valid pending changes.')
    if len({e.get('id') for e in edits}) != len(edits):
        raise ValueError('Each pending input must be distinct.')
    explicit = {e.get('id') for e in edits}
    for edit in edits:
        c = cells.get(edit.get('id'))
        if not c or c.get('editable') is not True:
            raise ValueError('Pending changes must select independent editable inputs.')
        value, suffix = parse_amount(edit.get('value', ''), statement['locale'])
        if suffix != c['suffix'] or (suffix and value < 0):
            raise ValueError('Preserve the printed S/H direction and a non-negative balance magnitude.')
        if statement.get('profile') == 'addison_susa' and c.get('column_index') in (1, 2, 3, 4) and value < 0:
            raise ValueError('SuSa debit and credit movements must be non-negative.')
        values[c['id']] = value
    for monthly, annual in statement.get('period_pairs', []):
        if monthly in explicit and annual not in explicit:
            values[annual] += values[monthly] - Decimal(cells[monthly]['value'])
    for rule in _order(_rules(statement)):
        values[rule['target']] = evaluate(rule, values)
    return values


def _result(definition, values):
    if definition['target']:
        return values[definition['target']]
    return sum((values[key] * coefficient for key, coefficient in definition['coefficients'].items()), Decimal(0))


def resolve(statement, edits, goal):
    if not isinstance(goal, dict) or goal.get('kind') not in ('profit', 'loss'):
        raise ValueError('Choose Profit or Loss for the desired result.')
    definition = next((p for p in _definitions(statement) if p['id'] == goal.get('period')), None)
    if definition is None:
        raise ValueError('Profit/loss is unavailable for this report or period.')
    if statement.get('profile') and not statement.get('verified'):
        raise ValueError('Source discrepancies must be resolved before setting profit/loss.')
    magnitude, suffix = parse_amount(goal.get('amount', ''), statement['locale'])
    if magnitude < 0 or suffix:
        raise ValueError('Enter a non-negative profit/loss amount without an S/H suffix; choose the sign with Profit or Loss.')
    desired = magnitude if goal['kind'] == 'profit' else -magnitude
    cells = {c['id']: c for c in statement['cells']}
    source = cells.get(goal.get('source'))
    values = _values(statement, edits)
    coefficient = _input_coefficients(statement, definition, {e['id'] for e in edits}).get(goal.get('source'))
    if not source or source.get('editable') is not True or coefficient not in (Decimal(-1), Decimal(1)):
        raise ValueError('Choose an editable revenue/expense input that contributes to the selected result.')
    before = _result(definition, values)
    delta = (desired - before) / coefficient
    adjusted = values[source['id']] + delta
    if adjusted.quantize(Decimal('.01')) != adjusted:
        raise ValueError('The requested result cannot be represented with two decimals.')
    merged = {e['id']: e['value'] for e in edits}
    merged[source['id']] = format_amount(adjusted, statement['locale'], source['suffix'])
    counterpart = None
    if statement.get('profile') == 'addison_susa':
        counterpart = cells.get(goal.get('counterpart'))
        opposite = {1: 2, 2: 1, 3: 4, 4: 3}[source['column_index']]
        if (not counterpart or counterpart.get('editable') is not True
                or not str(counterpart.get('row', '')).isdigit() or not 0 <= int(counterpart['row']) < 4000
                or counterpart.get('column_index') != opposite):
            raise ValueError('Choose a balance-sheet counterpart in the opposite debit/credit column for the same period.')
        if adjusted < 0 or values[counterpart['id']] + delta < 0:
            raise ValueError('This target would make a debit/credit movement negative. Choose another input or counterpart.')
        merged[counterpart['id']] = format_amount(values[counterpart['id']] + delta, statement['locale'])
    resolved = [{'id': key, 'value': value} for key, value in merged.items()
                if parse_amount(value, statement['locale'])[0] != Decimal(cells[key]['value'])]
    if not resolved:
        raise ValueError('The selected result is already reached; no amounts changed.')
    if len(resolved) > 30:
        raise ValueError('The result adjustment exceeds the thirty-input batch limit.')
    # Verify the entire original and changed graph, including SuSa balances.
    if statement.get('profile'):
        calculated = calculate_profile(statement, resolved)
    else:
        calculated = calculate(statement, resolved, _rules(statement))
    actual = _result(definition, _values(statement, resolved))
    if actual != desired:
        raise ValueError('Pending period changes conflict with this profit/loss target. Remove the conflicting monthly/year-to-date changes.')
    return {'edits': resolved, 'rules': _rules(statement), **calculated,
            'profit_loss': {'kind': goal['kind'], 'period': definition['label'],
                'before': format_amount(before, statement['locale']), 'after': format_amount(actual, statement['locale']),
                'source': source['id'], 'counterpart': counterpart['id'] if counterpart else None}}
