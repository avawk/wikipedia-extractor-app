import re
from datetime import datetime
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "ISOM3400StudentExtractor/1.0 (educational project)"
}
WIKI_BASE = "https://en.wikipedia.org/wiki/"
SKIP_SECTIONS = {
    "contents",
    "references",
    "external links",
    "see also",
    "notes",
}
SKIP_CLASSES = {
    "navbox",
    "mw-editsection",
    "reference",
    "noprint",
}


def to_title(topic):
    topic = str(topic).strip().replace("_", " ")
    return re.sub(r"\s+", " ", topic).strip()


def safe_filename(title):
    safe_title = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]', "_", str(title)
    ).strip().strip(".")
    return safe_title or "Wikipedia_article"


def numbered_filename(filename, number=2):
    name = str(filename)
    dot = name.rfind(".")
    if dot >= 0:
        base = name[:dot]
        extension = name[dot:]
    else:
        base = name
        extension = ""

    base = re.sub(r"(?: \(\d+\)|_\d+)$", "", base)
    return f"{base} ({number}){extension}"


def format_txt(article_title, article_url, sections):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"Source URL: {article_url}",
        f"Extraction timestamp: {timestamp}",
        "Wikipedia licence: CC BY-SA 4.0",
        "",
        str(article_title),
        "=" * len(str(article_title)),
        "",
    ]

    for section in sections:
        section_title = section["title"]
        lines += [section_title, "-" * len(section_title), ""]

        for block in section["blocks"]:
            if block["type"] == "paragraph":
                text = re.sub(r"\s+", " ", block["text"]).strip()
                if text:
                    lines += [text, ""]

            elif block["type"] == "subheading":
                text = re.sub(r"\s+", " ", block["text"]).strip()
                if text:
                    lines += [text, ""]

            elif block["type"] == "list":
                for number, item in enumerate(block["items"], 1):
                    marker = f"{number}. " if block["ordered"] else "- "
                    lines.append(marker + re.sub(r"\s+", " ", item).strip())
                lines.append("")

            elif block["type"] == "table":
                for row in block["rows"]:
                    if any(row):
                        lines.append(" | ".join(
                            re.sub(r"\s+", " ", str(cell)).strip()
                            for cell in row
                        ))
                lines.append("")

    return "\n".join(lines).strip() + "\n"


class WikipediaExtractor:
    def __init__(self, topic=None):
        self.error = None
        self.headers = HEADERS
        self.soup = None
        self.title = None
        self.url = ""
        self.output = ""

        if topic is not None:
            self.fetch_article(topic)

    def fetch_article(self, topic):
        self.error = None
        topic = str(topic).strip()
        if not topic:
            self.error = "Error: Topic cannot be empty."
            self.title = None
            return False

        url = WIKI_BASE + quote(topic.replace(" ", "_"), safe="_")
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            self.soup = BeautifulSoup(response.text, "html.parser")

            title = self.soup.find("h1", id="firstHeading")
            content = self.soup.find("div", id="mw-content-text")
            if title is None or content is None:
                raise ValueError("Wikipedia page structure is incomplete")

            self.title = title.get_text(" ", strip=True)
            self.url = response.url
            return True

        except requests.exceptions.HTTPError as error:
            code = getattr(error.response, "status_code", "unknown")
            self.error = f"Error: Article '{topic}' was not found (HTTP {code})."
        except requests.exceptions.ConnectionError:
            self.error = "Network error: Could not connect to Wikipedia."
        except requests.exceptions.Timeout:
            self.error = "Network error: The Wikipedia request timed out."
        except requests.exceptions.RequestException as error:
            self.error = f"Network error: {error}"
        except (AttributeError, ValueError, TypeError) as error:
            self.error = f"Error: Failed to parse the Wikipedia page ({error})."

        self.title = None
        return False

    def get_top_level_sections(self):
        if self.soup is None:
            return []

        content = self.soup.find("div", id="mw-content-text")
        if content is None:
            return []

        sections = []
        for heading in content.find_all("h2"):
            text = heading.get_text(" ", strip=True).replace("[edit]", "").strip()
            if text and text.lower() not in SKIP_SECTIONS:
                sections.append(text)
        return sections

    def section_titles(self):
        return self.get_top_level_sections()

    @staticmethod
    def clean_text(text):
        text = re.sub(r"\[\s*\d+(?:\s*[-–]\s*\d+)?\s*\]", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def extract_selected_sections(self, indexes):
        if self.soup is None:
            self.error = "Error: No article has been loaded."
            return False

        content = self.soup.find("div", id="mw-content-text")
        if content is None:
            self.error = "Error: Article content could not be found."
            return False

        headings = []
        for heading in content.find_all("h2"):
            text = heading.get_text(" ", strip=True).replace("[edit]", "").strip()
            if text and text.lower() not in SKIP_SECTIONS:
                headings.append((text, heading))

        lines = [self.title, "=" * len(self.title), ""]

        for index in indexes:
            if index >= len(headings):
                continue

            section_title, section_heading = headings[index]
            lines += [section_title, "-" * len(section_title), ""]

            started = False
            elements = content.find_all(
                ["h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table"]
            )

            for element in elements:
                if element.name == "h2":
                    if started:
                        break
                    if element is section_heading:
                        started = True
                    continue
                if not started:
                    continue

                if element.name.startswith("h"):
                    heading_text = self.clean_text(
                        element.get_text(" ", strip=True).replace("[edit]", "")
                    )
                    if heading_text:
                        lines += [heading_text, ""]

                elif element.name == "p":
                    paragraph = self.clean_text(
                        element.get_text(" ", strip=True)
                    )
                    if paragraph:
                        lines += [paragraph, ""]

                elif element.name in {"ul", "ol"}:
                    for number, item in enumerate(
                        element.find_all("li", recursive=False), 1
                    ):
                        item_text = self.clean_text(
                            item.get_text(" ", strip=True)
                        )
                        if item_text:
                            prefix = (
                                f"{number}. "
                                if element.name == "ol"
                                else "- "
                            )
                            lines.append(prefix + item_text)
                    lines.append("")

                elif element.name == "table":
                    for row in element.find_all("tr"):
                        cells = [
                            self.clean_text(
                                cell.get_text(" ", strip=True)
                            )
                            for cell in row.find_all(
                                ["th", "td"], recursive=False
                            )
                        ]
                        if any(cells):
                            lines.append(" | ".join(cells))
                    lines.append("")

        self.output = "\n".join(lines).strip() + "\n"
        return True

    def extract(self, title):
        sections = self.get_top_level_sections()
        indexes = [
            index
            for index, section_title in enumerate(sections)
            if section_title == title
        ]
        if not indexes:
            return {"title": title, "blocks": []}
        return self._extract_section(title, indexes[0])

    def _extract_section(self, title, index):
        content = self.soup.find("div", id="mw-content-text")
        headings = []
        for heading in content.find_all("h2"):
            text = heading.get_text(" ", strip=True).replace("[edit]", "").strip()
            if text and text.lower() not in SKIP_SECTIONS:
                headings.append((text, heading))

        if index >= len(headings):
            return {"title": title, "blocks": []}

        section_title, section_heading = headings[index]
        blocks = []
        started = False

        elements = content.find_all(
            ["h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table"]
        )
        for element in elements:
            if element.name == "h2":
                if started:
                    break
                if element is section_heading:
                    started = True
                continue
            if not started:
                continue

            if element.name.startswith("h"):
                text = self.clean_text(
                    element.get_text(" ", strip=True).replace("[edit]", "")
                )
                if text:
                    blocks.append({"type": "subheading", "text": text})

            elif element.name == "p":
                text = self.clean_text(element.get_text(" ", strip=True))
                if text:
                    blocks.append({"type": "paragraph", "text": text})

            elif element.name in {"ul", "ol"}:
                items = []
                for item in element.find_all("li", recursive=False):
                    text = self.clean_text(item.get_text(" ", strip=True))
                    if text:
                        items.append(text)
                if items:
                    blocks.append({
                        "type": "list",
                        "ordered": element.name == "ol",
                        "items": items,
                    })

            elif element.name == "table":
                rows = []
                for row in element.find_all("tr"):
                    cells = [
                        self.clean_text(
                            cell.get_text(" ", strip=True)
                        )
                        for cell in row.find_all(
                            ["th", "td"], recursive=False
                        )
                    ]
                    if any(cells):
                        rows.append(cells)
                if rows:
                    blocks.append({"type": "table", "rows": rows})

        return {"title": section_title, "blocks": blocks}
