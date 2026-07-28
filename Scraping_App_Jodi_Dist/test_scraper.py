import sys
import asyncio
import os
from main import main

dir_path = os.path.dirname(os.path.realpath(__file__))
template_file = os.path.join(dir_path, "Template_Test_37.xlsx")

if __name__ == '__main__':
    asyncio.run(main(template_file=template_file, scrape_detail=True, max_workers=25))
