"""Pytest configuration file to make fixtures available globally."""

# Import all fixtures to make them available across all tests
from tests.fixtures.common import (  # noqa: F401
    async_client,
    clean_caas_env,
    disable_rate_limiting,
    reset_task_manager,
    sample_scanned_pdf_bytes,
    sample_docx_bytes,
    sample_pdf_bytes,
    sample_pptx_bytes,
)

# Import format-specific fixtures
from tests.fixtures.xlsx import (  # noqa: F401
    sample_xlsx_bytes,
    sample_xlsx_simple_bytes,
    sample_xlsx_multi_sheet_bytes,
    sample_xlsx_merged_cells_bytes,
    sample_xlsx_dates_numbers_bytes,
    sample_xlsx_special_chars_bytes,
    sample_xlsx_empty_sheet_bytes,
)

from tests.fixtures.docx import (  # noqa: F401
    sample_docx_bytes,
)

from tests.fixtures.pdf import (  # noqa: F401
    sample_pdf_bytes,
    sample_pdf_with_link_bytes,
)

from tests.fixtures.html import (  # noqa: F401
    sample_html_bytes,
)

from tests.fixtures.odt import (  # noqa: F401
    sample_odt_bytes,
)

from tests.fixtures.odp import (  # noqa: F401
    sample_odp_bytes,
)

from tests.fixtures.ods import (  # noqa: F401
    sample_ods_bytes,
)

from tests.fixtures.pptx import (  # noqa: F401
    sample_pptx_bytes,
)

from tests.fixtures.batch import (  # noqa: F401
    pdf_bytes_1,
    pdf_bytes_2,
    docx_bytes,
)
