Replaced generic exceptions (ValueError, TypeError, Exception, etc.) in task contexts with
PulpException subclasses that carry unique error codes (RPM0001–RPM0018). This ensures that
error details are preserved when ``REDACT_UNSAFE_EXCEPTIONS`` is enabled, instead of being
sanitized into generic "An error occurred" messages.
