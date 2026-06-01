"""CAAS CLI entry point."""

import uvicorn
from app.config import settings


def main() -> None:
    """Run the CAAS server."""
    uvicorn.run(
        "app.api:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
