import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from requests_kerberos import HTTPKerberosAuth
from urllib3.util import parse_url
import re
import os
import logging

logger = logging.getLogger(__name__)

pd.set_option('future.no_silent_downcasting', True)
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

class HTTPAdapterWithProxyKerberosAuth(requests.adapters.HTTPAdapter):
    def proxy_headers(self, proxy):
        headers = {}
        auth = HTTPKerberosAuth()
        negotiate_details = auth.generate_request_header(None, parse_url(proxy).host, is_preemptive=True)
        headers['Proxy-Authorization'] = negotiate_details
        return headers

class GoogleSheetDownloader:
    """Class để tải và xử lý Google Sheet từ URL công khai, lưu dữ liệu và màu nền vào file Excel."""

    def __init__(self, spreadsheet_id: str, html_url: str, gid: str, proxies: Optional[dict] = None):
        """
        Khởi tạo với ID của Google Sheet và worksheet.

        Args:
            spreadsheet_id: ID của Google Sheet.
            html_url: URL HTML công khai của sheet (nếu có).
            gid: ID của worksheet.
            proxies: Dictionary chứa cấu hình proxy (nếu có).
        """
        self.spreadsheet_id = spreadsheet_id
        self.gid = gid
        self.html_url = html_url
        session = requests.Session()
        if False and (proxies is not None):
            session.proxies = proxies
            session.mount('http://', HTTPAdapterWithProxyKerberosAuth())
            session.mount('https://', HTTPAdapterWithProxyKerberosAuth())
        self.session = session

    def fetch_html(self) -> Tuple[str, str]:
        """Tải nội dung HTML từ Google Sheet qua /htmlview.

        Returns:
            Nội dung HTML của sheet.

        Raises:
            Exception: Nếu không thể truy cập sheet hoặc lỗi mạng.
        """
        html_url = self.html_url or f'https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/htmlview'
        logger.info(f"Tải HTML từ: {html_url}")
        try:
            response = self.session.get(html_url, verify=False)
            response.raise_for_status()
            return html_url, response.text
        except Exception as e:
            logger.error(f"Lỗi khi tải HTML: {e}")
            raise Exception(f"Lỗi khi tải HTML: {e}")

    def extract_css_colors(self, soup: BeautifulSoup) -> dict:
        """Trích xuất màu nền từ CSS classes trong thẻ <style>.

        Args:
            soup: Đối tượng BeautifulSoup chứa HTML.

        Returns:
            Dictionary ánh xạ CSS class sang mã màu hex.
        """
        css_colors = {}
        style_tag = soup.find('style')
        if not style_tag:
            logger.warning("Không tìm thấy thẻ <style> trong HTML.")
            return css_colors

        css_content = style_tag.get_text()
        pattern = r'\.ritz\s*\.waffle\s*\.s(\d+)\s*\{[^}]*background-color:\s*([^;]+);'
        matches = re.findall(pattern, css_content)

        for class_id, color in matches:
            color = color.strip()
            if color.startswith('rgb'):
                rgb = [int(x) for x in re.findall(r'\d+', color)]
                color = f"{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            css_colors[f's{class_id}'] = color

        logger.info(f"Đã trích xuất {len(css_colors)} màu nền từ CSS")
        return css_colors

    def parse_html_to_data(self, html_content: str) -> Tuple[List[List[str]], List[List[str]]]:
        """Parse HTML để lấy dữ liệu bảng và màu nền từ div có id khớp với gid.

        Args:
            html_content: Nội dung HTML của sheet.

        Returns:
            Tuple chứa danh sách dữ liệu và danh sách màu nền.

        Raises:
            Exception: Nếu không tìm thấy div, bảng hoặc dữ liệu.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            css_colors = self.extract_css_colors(soup)

            div = soup.find('div', id=self.gid.strip('#'))
            if not div:
                raise Exception(f"Không tìm thấy div với id={self.gid} trong HTML.")

            table = div.find('table')
            if not table:
                raise Exception(f"Không tìm thấy bảng dữ liệu trong div với id={self.gid}.")

            rows = table.find_all('tr')
            if not rows:
                raise Exception("Không có hàng nào trong bảng.")

            max_cols = max(
                sum(int(cell.get('colspan', 1)) for cell in row.find_all(['td', 'th']))
                for row in rows
            )

            data_grid = []
            color_grid = []
            merged_count = 0
            row_idx = 0

            for row in rows:
                while len(data_grid) <= row_idx:
                    data_grid.append([None] * max_cols)
                    color_grid.append([None] * max_cols)

                col_idx = 0
                cells = row.find_all(['td', 'th'])

                for cell in cells:
                    while col_idx < max_cols and data_grid[row_idx][col_idx] is not None:
                        col_idx += 1

                    rowspan = int(cell.get('rowspan', 1))
                    colspan = int(cell.get('colspan', 1))
                    cell_text = cell.get_text(strip=True)

                    classes = cell.get('class', [])
                    if 'freezebar-cell' in classes:
                        continue
                    bg_color = ''
                    for cls in classes:
                        if cls in css_colors:
                            bg_color = css_colors[cls]
                            break

                    # Đếm vùng merged để log
                    if rowspan > 1 or colspan > 1:
                        merged_count += 1

                    # Chỉ đặt giá trị cho ô đầu tiên, các ô khác để trống
                    for r in range(row_idx, min(row_idx + rowspan, len(rows))):
                        while len(data_grid) <= r:
                            data_grid.append([None] * max_cols)
                            color_grid.append([None] * max_cols)

                        for c in range(col_idx, min(col_idx + colspan, max_cols)):
                            if r == row_idx and c == col_idx:
                                data_grid[r][c] = cell_text
                            else:
                                data_grid[r][c] = ''
                            color_grid[r][c] = bg_color

                    col_idx += colspan

                row_idx += 1

            data = [[cell if cell is not None else '' for cell in row] for row in data_grid if any(cell is not None for cell in row)]
            colors = [[cell if cell is not None else '' for cell in row] for row in color_grid if any(cell is not None for cell in row)]

            if not data:
                raise Exception("Không có dữ liệu nào được lấy từ sheet.")

            logger.info(f"Đã xử lý {merged_count} vùng merged cells trong bảng")
            return data, colors
        except Exception as e:
            logger.error(f"Lỗi khi parse HTML: {e}")
            raise Exception(f"Lỗi khi parse HTML: {e}")

    def process_data(self, data: List[List[str]], colors: List[List[str]]) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """Xử lý dữ liệu và màu: bỏ hàng 1, cột 1, giữ nguyên các hàng rỗng ở giữa.

        Args:
            data: Danh sách dữ liệu từ HTML.
            colors: Danh sách màu nền từ HTML.

        Returns:
            Tuple chứa DataFrame dữ liệu và DataFrame màu nền.
        """
        try:
            data_df = pd.DataFrame(data)
            if data_df.empty:
                logger.warning("Dữ liệu rỗng sau khi bỏ hàng 1.")
                return None, None
            data_df = data_df.iloc[:, 1:]
            if data_df.empty:
                logger.warning("Dữ liệu rỗng sau khi bỏ cột 1.")
                return None, None

            color_df = pd.DataFrame(colors)
            if color_df.empty:
                logger.warning("Màu nền rỗng sau khi bỏ hàng 1.")
                return data_df, None
            color_df = color_df.iloc[:, 1:]
            if color_df.empty:
                logger.warning("Màu nền rỗng sau khi bỏ cột 1.")
                return data_df, None

            # Thay thế chuỗi rỗng và khoảng trắng bằng np.nan, nhưng giữ nguyên cấu trúc
            data_df = data_df.replace(r'^\s*$', np.nan, regex=True)
            data_df = data_df.replace('', np.nan)

            # Đồng bộ kích thước của color_df với data_df
            color_df = color_df.loc[:data_df.index[-1], :data_df.columns[-1]]

            if data_df.empty:
                logger.warning("Dữ liệu rỗng sau khi xử lý.")
                return None, None
            logger.info(f"Đã xử lý dữ liệu: {data_df.shape[0]} hàng, {data_df.shape[1]} cột")
            return data_df, color_df
        except Exception as e:
            logger.error(f"Lỗi khi xử lý dữ liệu: {e}")
            raise Exception(f"Lỗi khi xử lý dữ liệu: {e}")

    def download(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], str]:
        """
        Tải Google Sheet, xử lý, và trả về DataFrame dữ liệu, DataFrame màu sắc, và URL.

        Args:
            return_df: Nếu True, sẽ trả về DataFrames thay vì lưu file.

        Returns:
            Một tuple chứa (data_df, color_df, download_url).
        """
        download_url = ''
        try:
            download_url, html_content = self.fetch_html()
            data, colors = self.parse_html_to_data(html_content)
            data_df, color_df = self.process_data(data, colors)

            if data_df is None:
                logger.warning("Dữ liệu rỗng sau khi xử lý.")
                return None, None, download_url

            return data_df, color_df, download_url

        except Exception as e:
            logger.error(f"Lỗi khi tải và xử lý Google Sheet: {e}")
            return None, None, download_url
