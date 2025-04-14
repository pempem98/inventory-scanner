import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Optional

class GoogleSheetDownloader:
    """Class để tải và xử lý Google Sheet từ URL công khai."""

    def __init__(self, spreadsheet_id: str, gid: str):
        """
        Khởi tạo với ID của Google Sheet và worksheet.

        Args:
            spreadsheet_id: ID của Google Sheet.
            gid: ID của worksheet.
        """
        self.spreadsheet_id = spreadsheet_id
        self.gid = gid

    def fetch_html(self) -> str:
        """Tải nội dung HTML từ Google Sheet qua /htmlview."""
        html_url = f'https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/htmlview?gid={self.gid}'
        try:
            response = requests.get(html_url)
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

                        for c in range(col_idx, min(col_idx + colspan, max_cols)):
                            grid[r][c] = cell_text

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
        """Xử lý dữ liệu: bỏ hàng 1, cột 1, trả về DataFrame."""
        try:
            df = pd.DataFrame(data[1:])
            if df.empty:
                return None
            df = df.iloc[:, 1:]
            if df.empty:
                return None
            return df
        except Exception as e:
            raise Exception(f"Lỗi khi xử lý dữ liệu: {e}")

    def save_to_excel(self, df: pd.DataFrame, output_file: str) -> None:
        """Lưu DataFrame thành file XLSX, không có index và header."""
        try:
            df.to_excel(output_file, index=False, header=False)
            print(f"Đã lưu dữ liệu vào {output_file}")
        except Exception as e:
            raise Exception(f"Lỗi khi lưu file XLSX: {e}")

    def download(self, output_file: str = 'downloaded_sheet.xlsx') -> None:
        """Tải Google Sheet, bỏ hàng 1, cột 1, lưu thành XLSX."""
        try:
            html_content = self.fetch_html()
            data = self.parse_html_to_data(html_content)
            df = self.process_data(data)
            if df is None:
                print("Dữ liệu rỗng sau khi bỏ hàng 1 và cột 1.")
                return
            self.save_to_excel(df, output_file)
        except Exception as e:
            print(f"Lỗi: {e}")
            print("Kiểm tra xem sheet có công khai hoặc cho phép xem qua link không.")

# Chạy với thông tin từ URL
if __name__ == "__main__":
    downloader = GoogleSheetDownloader(
        spreadsheet_id='1wxSFdMeIwHcijdeqOj0oFQcFGqi_8RFT',
        gid='723417714'
    )
    downloader.download()
