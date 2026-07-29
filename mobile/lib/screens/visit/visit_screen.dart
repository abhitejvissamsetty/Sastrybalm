import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class VisitScreen extends StatelessWidget {
  const VisitScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Visit Manager')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.storefront_rounded,
                  size: 64, color: theme.colorScheme.primary),
              const SizedBox(height: 16),
              Text(
                'Manage Visits',
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Please select an outlet from the Beat Plan route to check in and begin logging a visit.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => context.go('/beat'),
                child: const Text('Go to Beat Plan'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
