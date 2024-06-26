import requests
from bs4 import BeautifulSoup
import logging
import pandas as pd
import os

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Extract PS1 DataCenter Started")

    url = "https://psxdatacenter.com/ntsc-u_list.html"
    response = requests.get(url)

    if response.status_code == 200:
        content = response.text
    else:
        print("Failed to get page content:", response.status_code)

    soup = BeautifulSoup(content, "html.parser")
    frame = soup.find("frame", {"name": "ulist"})
    frame_src = frame["src"]
    frame_url = f"https://psxdatacenter.com/{frame_src}"
    frame_response = requests.get(frame_url)

    frame_soup = BeautifulSoup(frame_response.content, "html.parser")
    tables = frame_soup.find_all("table", {"class": "sectiontable"})

    all_dfs = []
    for i, table in enumerate(tables):
        table_data = []
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all(["td", "th"])
            cols = [col.get_text(strip=True) for col in cols]
            if len(cols) > 1:
                cols[1] = " ".join(cols[1].split())
            table_data.append(cols)

        if table_data:
            df = pd.DataFrame(table_data)
            all_dfs.append(df)

    df_extract = pd.concat(all_dfs, ignore_index=True)
    df_extract.columns = ["Info", "Disk_Code", "Name", "Language"]

#    path_extract = os.environ["DATACENTER_EXTRACT_OUTPUT_PATH"]
    df_extract.to_csv(f"extracted_ps1_datacenter.csv")

    logger.info("Extract PS1 DataCenter Finished")


if __name__ == "__main__":
    main()