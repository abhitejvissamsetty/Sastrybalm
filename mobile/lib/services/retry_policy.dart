import 'dart:async';

class RetryPolicy {
  final int maximumAttempts;
  final Duration initialDelay;
  final Future<void> Function(Duration) delay;

  RetryPolicy({
    this.maximumAttempts = 3,
    this.initialDelay = const Duration(milliseconds: 500),
    Future<void> Function(Duration)? delay,
  }) : delay = delay ?? Future<void>.delayed;

  Future<T> execute<T>(
    Future<T> Function() operation, {
    required bool Function(Object error) shouldRetry,
  }) async {
    Object? lastError;
    StackTrace? lastStack;
    for (var attempt = 1; attempt <= maximumAttempts; attempt++) {
      try {
        return await operation();
      } catch (error, stack) {
        lastError = error;
        lastStack = stack;
        if (attempt == maximumAttempts || !shouldRetry(error)) {
          Error.throwWithStackTrace(error, stack);
        }
        await delay(initialDelay * (1 << (attempt - 1)));
      }
    }
    Error.throwWithStackTrace(lastError!, lastStack!);
  }
}
