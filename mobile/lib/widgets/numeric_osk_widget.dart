import 'package:flutter/material.dart';

class NumericOskWidget extends StatelessWidget {
  final ValueChanged<String> onKeyPress;
  final VoidCallback onDelete;
  final VoidCallback onNext;
  final String nextLabel;

  const NumericOskWidget({
    super.key,
    required this.onKeyPress,
    required this.onDelete,
    required this.onNext,
    this.nextLabel = 'NEXT',
  });

  Widget _buildKey(BuildContext context, String label,
      {VoidCallback? onTap,
      Color? color,
      Color? textColor,
      bool isAction = false}) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    final defaultBg =
        isDark ? const Color(0xFF18181B) : const Color(0xFFF4F4F5);
    final defaultFg =
        isDark ? const Color(0xFFFAFAFA) : const Color(0xFF09090B);
    final borderColor =
        isDark ? const Color(0xFF27272A) : const Color(0xFFE4E4E7);

    return Expanded(
      child: Padding(
        padding: const EdgeInsets.all(4.0),
        child: Material(
          color: color ?? defaultBg,
          borderRadius: BorderRadius.circular(10),
          child: InkWell(
            onTap: onTap ?? () => onKeyPress(label),
            borderRadius: BorderRadius.circular(10),
            child: Container(
              height: 52,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: borderColor, width: 1.0),
              ),
              alignment: Alignment.center,
              child: Text(
                label,
                style: TextStyle(
                  fontSize: isAction ? 15 : 20,
                  fontWeight: FontWeight.bold,
                  color: textColor ?? defaultFg,
                  letterSpacing: isAction ? 0.5 : 0,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    final primaryBg =
        isDark ? const Color(0xFFFAFAFA) : const Color(0xFF09090B);
    final primaryFg =
        isDark ? const Color(0xFF09090B) : const Color(0xFFFAFAFA);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 10.0),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF09090B) : const Color(0xFFFFFFFF),
        border: Border(
            top: BorderSide(
                color:
                    isDark ? const Color(0xFF27272A) : const Color(0xFFE4E4E7),
                width: 1.0)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              _buildKey(context, '1'),
              _buildKey(context, '2'),
              _buildKey(context, '3'),
            ],
          ),
          Row(
            children: [
              _buildKey(context, '4'),
              _buildKey(context, '5'),
              _buildKey(context, '6'),
            ],
          ),
          Row(
            children: [
              _buildKey(context, '7'),
              _buildKey(context, '8'),
              _buildKey(context, '9'),
            ],
          ),
          Row(
            children: [
              _buildKey(context, '⌫', onTap: onDelete),
              _buildKey(context, '0'),
              _buildKey(
                context,
                nextLabel,
                onTap: onNext,
                color: primaryBg,
                textColor: primaryFg,
                isAction: true,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
