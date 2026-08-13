from weasyprint import HTML
import os

def convert_html_to_pdf(html_content, html_filename):
    """
    Converts HTML content to a PDF.

    Args:
        html_content (str): The HTML content to be converted.
        html_filename (str): The original filename of the HTML report.

    Returns:
        tuple: A tuple containing the PDF content (bytes) and the new PDF filename (str).
    """
    # Create the PDF filename by replacing the .html extension with .pdf
    pdf_filename = os.path.splitext(html_filename)[0] + ".pdf"

    # Convert the HTML string content to a PDF, returning the raw bytes
    # pdf_content = HTML(string=html_content, base_url="/app").write_pdf()

    base_path = f"file://{os.path.abspath(os.getcwd())}/"
    pdf_content = HTML(string=html_content, base_url=base_path).write_pdf()

    return pdf_content, pdf_filename