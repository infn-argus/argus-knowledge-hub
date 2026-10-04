"""Keep capability tokens out of logs.

A single-use download token may arrive in a query string (`?token=…`) when a client cannot send a
header. Access logs, here and in front of ARGUS, must not keep it: this filter rewrites the request
line uvicorn logs; operations.md lists the proxy settings that do the same upstream.
"""
import logging
import re

SECRET_QUERY = re.compile(r"(?i)([?&](?:token|download_token|access_token|code)=)[^&\s\"]+")


def redact(text: str) -> str:
    return SECRET_QUERY.sub(r"\1[redacted]", text)


class RedactTokens(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def install() -> None:
    for name in ("uvicorn.access", "uvicorn.error", "httpx"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactTokens) for f in logger.filters):
            logger.addFilter(RedactTokens())


install()
