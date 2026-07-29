import 'package:flutter/material.dart';

class DenominationInput extends StatefulWidget {
  final double totalAmount;
  final ValueChanged<Map<String, int>> onChanged;

  const DenominationInput({
    super.key,
    required this.totalAmount,
    required this.onChanged,
  });

  @override
  State<DenominationInput> createState() => _DenominationInputState();
}

class _DenominationInputState extends State<DenominationInput> {
  final _denoms = [2000, 500, 200, 100, 50, 20, 10];
  final Map<int, int> _counts = {};

  double get _totalFromDenoms =>
      _denoms.fold(0.0, (sum, d) => sum + d * (_counts[d] ?? 0));

  bool get _isValid => _totalFromDenoms == widget.totalAmount;

  @override
  Widget build(BuildContext context) {
    final diff = _totalFromDenoms - widget.totalAmount;
    final theme = Theme.of(context);

    return Column(
      children: [
        ..._denoms.map((denom) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              children: [
                SizedBox(
                  width: 70,
                  child: Text(
                    '₹$denom',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Text('×  ', style: theme.textTheme.bodyMedium),
                SizedBox(
                  width: 80,
                  child: TextField(
                    keyboardType: TextInputType.number,
                    onChanged: (v) {
                      setState(() {
                        _counts[denom] = int.tryParse(v) ?? 0;
                        widget.onChanged({
                          for (var d in _denoms) d.toString(): _counts[d] ?? 0,
                        });
                      });
                    },
                    decoration: InputDecoration(
                      filled: true,
                      fillColor:
                          theme.colorScheme.primary.withValues(alpha: 0.05),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding:
                          const EdgeInsets.symmetric(horizontal: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  '= ₹${(denom * (_counts[denom] ?? 0)).toStringAsFixed(0)}',
                  style: theme.textTheme.bodyMedium,
                ),
              ],
            ),
          );
        }),
        Divider(color: theme.dividerColor),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Total Denoms',
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.bold)),
            Text(
              '₹${_totalFromDenoms.toStringAsFixed(0)}',
              style: TextStyle(
                color: _isValid ? Colors.green.shade600 : Colors.red.shade600,
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
          ],
        ),
        if (!_isValid && _totalFromDenoms > 0)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(
              diff > 0
                  ? 'Excess: ₹${diff.abs().toStringAsFixed(0)}'
                  : 'Short: ₹${diff.abs().toStringAsFixed(0)}',
              style: TextStyle(
                  color: Colors.red.shade600,
                  fontSize: 12,
                  fontWeight: FontWeight.bold),
            ),
          ),
      ],
    );
  }
}
