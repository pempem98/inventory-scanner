import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from typing import List, Optional
from requests_kerberos import HTTPKerberosAuth
from urllib3.util import parse_url

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
    """Class để tải và xử lý Google Sheet từ URL công khai."""

    def __init__(self, spreadsheet_id: str, gid: str, proxies=None):
        """
        Khởi tạo với ID của Google Sheet và worksheet.

        Args:
            spreadsheet_id: ID của Google Sheet.
            gid: ID của worksheet.
            proxies: Dictionary chứa cấu hình proxy (nếu có).
        """
        self.spreadsheet_id = spreadsheet_id
        self.gid = gid
        session = requests.Session()
        if proxies is not None:
            session.proxies = proxies
            session.mount('http://', HTTPAdapterWithProxyKerberosAuth())
            session.mount('https://', HTTPAdapterWithProxyKerberosAuth())
        self.session = session

    def fetch_html(self) -> str:
        """Tải nội dung HTML từ Google Sheet qua /htmlview."""
        html_url = f'https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/htmlview?gid={self.gid}'
        print(f"Goto: {html_url}")
        try:
            response = self.session.get(html_url, verify=False)
            if response.status_code == 200:
                return response.text
            raise Exception(f"Không thể truy cập sheet. Mã lỗi: {response.status_code}")
        except Exception as e:
            raise Exception(f"Lỗi khi tải HTML: {e}")

    def parse_html_to_data(self, html_content: str) -> List[List[str]]:
        """Parse HTML để lấy dữ liệu bảng từ div có id khớp với gid, xử lý colspan và rowspan."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # Tìm div có id khớp với gid
            div = soup.find('div', id=self.gid)
            if not div:
                raise Exception(f"Không tìm thấy div với id={self.gid} trong HTML.")

            # Tìm bảng bên trong div
            table = div.find('table')
            if not table:
                raise Exception(f"Không tìm thấy bảng dữ liệu trong div với id={self.gid}.")

            # Lấy tất cả các hàng
            rows = table.find_all('tr')
            if not rows:
                raise Exception("Không có hàng nào trong bảng.")

            # Xác định số cột tối đa
            max_cols = 0
            for row in rows:
                col_count = sum(
                    int(cell.get('colspan', 1))
                    for cell in row.find_all(['td', 'th'])
                )
                max_cols = max(max_cols, col_count)

            # Khởi tạo lưới dữ liệu
            grid = []
            row_idx = 0

            for row in rows:
                # Thêm hàng mới vào grid nếu cần
                while len(grid) <= row_idx:
                    grid.append([None] * max_cols)

                col_idx = 0
                cells = row.find_all(['td', 'th'])

                for cell in cells:
                    # Tìm vị trí cột trống tiếp theo
                    while col_idx < max_cols and grid[row_idx][col_idx] is not None:
                        col_idx += 1

                    # Lấy giá trị rowspan và colspan, mặc định là 1
                    rowspan = int(cell.get('rowspan', 1))
                    colspan = int(cell.get('colspan', 1))
                    cell_text = cell.get_text(strip=True)

                    # Điền giá trị vào grid
                    for r in range(row_idx, min(row_idx + rowspan, len(rows))):
                        # Thêm hàng mới nếu cần
                        while len(grid) <= r:
                            grid.append([None] * max_cols)

                        grid[r][col_idx] = cell_text

                    col_idx += colspan

                row_idx += 1

            # Chuyển grid thành danh sách dữ liệu
            data = [[cell if cell is not None else '' for cell in row] for row in grid if any(cell is not None for cell in row)]

            if not data:
                raise Exception("Không có dữ liệu nào được lấy từ sheet.")

            # In 10 hàng đầu tiên để debug
            # if len(data) < 10:
            #     print(table.prettify())
            return data
        except Exception as e:
            raise Exception(f"Lỗi khi parse HTML: {e}")

    def process_data(self, data: List[List[str]]) -> Optional[pd.DataFrame]:
        """Xử lý dữ liệu: bỏ hàng 1, cột 1, xóa các hàng rỗng ở cuối, trả về DataFrame."""
        try:
            df = pd.DataFrame(data[1:])  # Bỏ hàng đầu tiên
            if df.empty:
                return None
            df = df.iloc[:, 1:]  # Bỏ cột đầu tiên
            if df.empty:
                return None
            
            # Thay thế chuỗi rỗng hoặc khoảng trắng bằng NaN
            df = df.replace(r'^\s*$', np.nan, regex=True)
            df = df.replace('', np.nan)
            
            # Xóa các hàng mà tất cả giá trị đều là NaN
            df = df.dropna(how='all')
            
            if df.empty:
                return None
            return df
        except Exception as e:
            raise Exception(f"Lỗi khi xử lý dữ liệu: {e}")

    def save_to_excel(self, df: pd.DataFrame, output_file: str) -> None:
        """Lưu DataFrame thành file XLSX hoặc CSV, không có index và header."""
        try:
            if output_file.endswith(".csv"):
                df.to_csv(output_file, index=False, header=False, encoding="utf-8")
            else:
                df.to_excel(output_file, index=False, header=False, engine="openpyxl")
            print(f"Đã lưu dữ liệu vào {output_file}")
        except Exception as e:
            raise Exception(f"Lỗi khi lưu file: {e}")

    def download(self, output_file: str = 'downloaded_sheet.xlsx') -> None:
        """Tải Google Sheet, bỏ hàng 1, cột 1, xóa hàng rỗng ở cuối, lưu thành file."""
        try:
            html_content = self.fetch_html()
            data = self.parse_html_to_data(html_content)
            df = self.process_data(data)
            if df is None:
                print("Dữ liệu rỗng sau khi xử lý.")
                return
            self.save_to_excel(df, output_file)
        except Exception as e:
            print(f"Lỗi: {e}")
            print("Kiểm tra xem sheet có công khai hoặc cho phép xem qua link không.")

# Chạy với thông tin từ URL
if __name__ == "__main__":
    proxies = {
        'http': 'http://rb-proxy-apac.bosch.com:8080',
        'https': 'http://rb-proxy-apac.bosch.com:8080'
    }
    downloader = GoogleSheetDownloader(
        spreadsheet_id='1O_JiM4VD0VlC1X0LmnvX5_eKpLCbzom8',
        gid='1453345957',
        proxies=proxies
    )
    downloader.download(output_file="downloaded_sheet.csv")
