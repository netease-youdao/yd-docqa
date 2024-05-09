from io import BytesIO
import json
import math
from typing import Any, Iterable
import os
import cv2
from paddleocr import PPStructure, PaddleOCR
import fitz
from PIL import Image
from kernel.utils import cur_func_name

from qanything_kernel.utils.custom_log import debug_logger




def _get_pdf_name(pdfPath):
    pdf_name = os.path.basename(pdfPath)
    pdf_name, _ex = os.path.splitext(pdf_name)
    return pdf_name


# 将PDF转换为图片，用于后去标题识别
def _pdf_to_image(pdfDoc, pdfPath, imagePath):
    pdf_name = _get_pdf_name(pdfPath)
    images_paths = []
    imagePath = f"{imagePath}/{pdf_name}"
    for pg in range(pdfDoc.page_count):
        page = pdfDoc[pg]

        mat = fitz.Matrix(1, 1)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        if not os.path.exists(imagePath):
            os.makedirs(imagePath)
        image = f"{imagePath}/page_{pg}.png"
        pix.save(image)
        images_paths.append({"page_number": pg, "img_path": image})
    return images_paths


def _save_pdf_content_image(custom_images: list, doc: Any, page_number: int,
                            pdf_name: str, _pdf_process_images_save_path):
    cur_page_images = []
    for img_index, img_info in enumerate(custom_images):
        img_index += 1
        base_image = doc.extract_image(img_info["xref"])
        image_bytes = base_image["image"]
        # 将图像字节转换为PIL Image对象
        pil_image = Image.open(BytesIO(image_bytes))
        save_path = f"{_pdf_process_images_save_path}/{pdf_name}"
        save_image_name = f"page_{page_number}_{img_index}.png"
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        pil_image.save(f"{save_path}/{save_image_name}")
        cur_page_images.append({
            "image_path": f"{save_path}/{save_image_name}",
            "desc": None,
            "area": img_info["area"]
        })
    return cur_page_images


# 获取中心点坐标距离[左上角x，左上角y，右下角x，右下角y]
def _calculate_distance(rect1, rect2):
    x1, y1 = ((rect1[0] + rect1[2]) / 2, (rect1[1] + rect1[3]) / 2)
    x2, y2 = ((rect2[0] + rect2[2]) / 2, (rect2[1] + rect2[3]) / 2)
    distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return distance


# 识别图片文字信息（用于补充到pdf文本内容中方便检索）
def _get_image_info_by_ocr(image: str):

    def _ocr_text_rect_sort(rect):
        return (rect[0][1], rect[0][0])

    image_text = ""
    ocr = PaddleOCR(lang="ch")
    result = ocr.ocr(image, cls=True)
    if result is None or len(result) <= 0 or (len(result) == 1 and result[0] is None):
        return None, None
    if len(result) == 1:
        image_infos = result[0]
    else:
        image_infos = result#[0]
    custom_info_data = []
    """
    image_infos 的结构是：
    [
        [[309.0, 395.0], [419.0, 395.0], [419.0, 425.0], [309.0, 425.0]], 
        ('声音浑浊', 0.9551941156387329)
    ]
    """
    texts = ""
    lines = []
    for item in image_infos:
        texts += item[1][0]
        bbox_x = int(item[0][0][0]) 
        bbox_y = int(item[0][0][1]) 
        bbox_w = int(item[0][1][0]) - bbox_x
        bbox_h = int(item[0][2][1]) - bbox_y
        line = {
            "line_bbox": f"{bbox_x}, {bbox_y}, {bbox_w}, {bbox_h}",
            "line_fontsize": max(bbox_h - 2, 6), # 行高最小不能低于6个像素。
            "line_text": item[1][0]
        }
        lines.append(line)
    return texts, lines



def _images_sort(image):
    return (image["area"][3], image["area"][0])


# 为整个文档划分段落
def _design_chapter(pdf_result: list):
    chapters = []
    # 将所有页面的block组装到一个大数组中
    blocks = []
    for i in range(0, len(pdf_result)):
        cur_page_blocks = pdf_result[i]["text_blocks"]
        for cur_page_block in cur_page_blocks:
            # 将page_number放入元素中，是为了更精准的构造matedata
            cur_page_block["page_number"] = i
        blocks.extend(cur_page_blocks)

    # 找到类型为标题的元素的索引
    indices = [
        index for index, value in enumerate(blocks) if value["type"] == "title"
    ]
    if not indices:
        chapters.append(blocks)
    else:
        indices = sorted(indices, key=lambda x: x)
        # 判断0是否包含在indices里面，直接获取索引小于当前索引且大于上一个索引的block组成段落，需要将0单独处理
        for i in range(0, len(indices)):
            if i == 0 and indices[i] != 0:
                chapters.append(blocks[:indices[i]])
            else:
                if i == len(indices) - 1:
                    chapters.append(blocks[indices[i]:])
                else:
                    chapters.append(blocks[indices[i]:indices[i + 1]])

    return chapters


# 删除页脚和页眉
def _delete_head_and_foot(text_blocks: list, head_areas: list,
                          foot_areas: list):
    should_be_deleted_blocks_index = []
    for i in range(0, len(text_blocks)):
        for header in head_areas:
            cur_distance = _calculate_distance(text_blocks[i]["area"],
                                               header["area"])
            if cur_distance <= 10 and i not in should_be_deleted_blocks_index:
                should_be_deleted_blocks_index.append(i)
        for foot in foot_areas:
            cur_distance = _calculate_distance(text_blocks[i]["area"],
                                               foot["area"])
            if cur_distance <= 10 and i not in should_be_deleted_blocks_index:
                should_be_deleted_blocks_index.append(i)
    text_blocks_to_ret = []
    for i, item in enumerate(text_blocks):
        if i in should_be_deleted_blocks_index:
            continue
        text_blocks_to_ret.append(item)

    return text_blocks_to_ret


# 获取PDF文档内容中的标题、表格的位置
def get_pdf_areas(pdfDoc, pdfPath: str, table_engine, _pdf_page_pixmap_save_path):
    img_paths = _pdf_to_image(pdfDoc, pdfPath, _pdf_page_pixmap_save_path)
    structrue_result = []
    for image in img_paths:
        img = cv2.imread(image["img_path"])
        pg = image["page_number"]
        page = table_engine(img, return_ocr_result_in_table=True)
        if page is not None:
            new_page = []
            for line in page:
                line.pop("img")
                new_page.append({"type": line["type"], "area": line["bbox"]})
            new_page = sorted(new_page, key=lambda x: x["area"][3])
            structrue_result.append({"page_number": pg, "layout": new_page})
    return structrue_result


# 获取pdf中的图片信息（识别图片文字信息）
def get_pdf_images(doc, pdfPath, temp_dir):
    pdf_name = _get_pdf_name(pdfPath)
    pdf_images = []
    # 循环每一页，获取图片信息
    for page_number in range(doc.page_count):
        page = doc[page_number]
        images = page.get_images(full=True)
        custom_images = []
        if len(images) > 0:
            for image in images:
                info = page.get_image_bbox(image)
                custom_image = {
                    "xref":
                    image[0],
                    "area": (int(round(info.x0)), int(round(info.y0)),
                             int(round(info.x1)), int(round(info.y1)))
                }
                custom_images.append(custom_image)
        cur_page_images = []
        if len(custom_images) > 0:
            custom_images = sorted(custom_images, key=_images_sort)  #按y,x轴排序
            # 循环单页中的图片集合，保存到本地用于OCR识别
            cur_page_images = _save_pdf_content_image(custom_images, doc,
                                                      page_number, pdf_name, temp_dir)
        pdf_images.append({
            "page_number": page_number,
            "images": cur_page_images
        })
    # OCR识别
    if len(pdf_images) > 0:
        for item in pdf_images:
            if len(item["images"]) <= 0:
                continue
            for image in item["images"]:
                desc, image_lines = _get_image_info_by_ocr(image["image_path"])
                image["desc"] = (desc, image_lines)
    return pdf_images

# 标记好标题块（用于后续段落划分）
def _sign_title_blocks(text_blocks: list, title_areas: list):
    for title_area in title_areas:
        for block in text_blocks:
            distance = _calculate_distance(block["area"], title_area)
            if distance <= 10:
                block["type"] = "title"
    return text_blocks

# 替换图片部分
def _replace_image_area(text_blocks: list, cur_page_images: list):
    for block in text_blocks:
        for item_image in cur_page_images:
            distance = _calculate_distance(block["area"], item_image["area"])
            if distance < 10:
                """
                block 是dict，包含3个字段：area, text, type(如图片就是"image")

                item_image['desc'] 是二元组，第一部分是所有文本拼起来的一个字符串，第二部分是lines list
                """
                block['text'] = item_image['desc'][0]
                lines = item_image['desc'][1]
                block['locations'] = [{
                    'bbox': block['area'],
                    'lines': lines,
                    'page_h': None,
                    'page_w': None,
                    'page_id': None
                }]
    return text_blocks

# 入参的bbox，都是 xyxy 形式
def bbox2_contains_bbox1_center(bbox1, bbox2):
    center_x = 0.5 * (bbox1[0] + bbox1[2])
    center_y = 0.5 * (bbox1[1] + bbox1[3])
    if center_x >= bbox2[0] and center_x <= bbox2[2] and center_y >= bbox2[1] and center_y <= bbox2[3]:
        return True
    else:
        return False

def assign_text_blocks_to_paragraphs(text_blocks, cur_page_layout):
    # 创建一个字典，用于存储每个段落的文本
    paragraph_texts = {}

    # 遍历每个文本行块
    for block in text_blocks:
        if block.get('type') not in ['text']:
            continue
        block_area = block['area']

        # 遍历每个段落框框
        for layout in cur_page_layout:
            layout_area = tuple(layout['area'])

            # 如果文本块在段落框框内
            if bbox2_contains_bbox1_center(block_area, layout_area):
                # 将文本块添加到对应段落的文本列表中
                # 要顺便把 locations 中的lines信息给填进去
                line_x = int(block_area[0])
                line_y = int(block_area[1])
                line_w = int(block_area[2]) - line_x
                line_h = int(block_area[3]) - line_y
                line = {
                    "line_bbox": f"{line_x}, {line_y}, {line_w}, {line_h}",
                    "line_fontsize": max(line_h - 2, 6), # 行高最小不能低于6个像素。
                    "line_text": block['text']
                }
                paragraph_texts.setdefault(layout_area, []).append(line)
                block['belongs_to_para'] = layout_area # 记一下当前文本行属于哪个段落了
                break  # 假设文本块只属于一个段落，因此找到对应段落后跳出循环


    # 遍历文本行们，跳过已经属于段落的那些
    new_text_blocks = []
    processed_paras = set()
    for block in text_blocks:
        if 'belongs_to_para' in block and block['belongs_to_para']: # 说明是需要跳过的，但如果是第一次遇到，就要把对应的段落给加到最终结果里
            layout_area = block['belongs_to_para']
            if layout_area not in processed_paras:
                # 第一次遇到这个段落，那就加入最终结果
                # 创建一个段落文本块
                paragraph_block = {
                    'area': layout_area,
                    'text': '\n'.join([x['line_text'] for x in paragraph_texts[layout_area]]),
                    'locations': [{
                        'bbox': layout_area,
                        'lines': paragraph_texts[layout_area],
                        'page_h': None,
                        'page_w': None,
                        'page_id': None
                    }],
                    'type': 'paragraph'
                }
                new_text_blocks.append(paragraph_block)
                processed_paras.add(layout_area)
        else:
            # new_text_blocks.append(block)

            # [deprecated] 不属于任何段落的文本块，就自成一段。
            # 不属于任何段落的文本块，就直接扔掉。一般就是无意义的页眉页脚啥的。
            pass

    return new_text_blocks


"""
用 pymupdf + ppstructure 解析的结果，要对齐到速读原有解析格式上来。
"""
def pdf_parse_to_chapters(pdf_path, temp_dir):
    engine = PPStructure(table=False, ocr=False, show_log=True, layout=True)
    doc = fitz.open(pdf_path)
    layouts = get_pdf_areas(doc, pdf_path, engine, temp_dir)
    images = get_pdf_images(doc, pdf_path, temp_dir)
    result = []
    for page_number in range(doc.page_count):
        page = doc[page_number]
        rect = page.rect
        page_width = rect.width  # 页面宽度
        page_height = rect.height  # 页面高度
        # 获取当前页的构造信息
        cur_page_layout = (list(
            filter(lambda x: x.get('page_number') == page_number,
                   layouts)))[0]["layout"]

        # 从当前页的构造信息中获取Title信息
        cur_page_title = list(
            filter(lambda x: x.get('type') == "title", cur_page_layout))
        title_areas = [area["area"] for area in cur_page_title]

        # 从当前页获取图片信息
        cur_page_images = (list(
            filter(lambda x: x.get('page_number') == page_number,
                   images)))[0]["images"]
        # 当前页的页眉
        cur_page_head = list(
            filter(lambda x: x.get('type') == "header", cur_page_layout))
        # 当前页的页脚
        cur_page_foot = list(
            filter(lambda x: x.get('type') == "footer", cur_page_layout))
        text_blocks = page.get_text("blocks")
        text_blocks = [{
            "area": (int(round(block[0])), int(round(block[1])),
                     int(round(block[2])), int(round(block[3]))),
            "text":
            block[4],
            "type":
            "text" if "<image:" not in block[4] else "image"
        } for block in sorted(text_blocks, key=lambda x: x[3])]
        # 删除页脚和页眉
        text_blocks = _delete_head_and_foot(text_blocks, cur_page_head,
                                            cur_page_foot)

        # 把可解析文本行放进 ppstructure 检测出的段落块中。
        # 规则是：遍历每个行bbox，行bbox的中点落在哪个段落bbox，就算属于哪个段落，忽略多个段落框柱了同一行的情况。
        text_blocks = assign_text_blocks_to_paragraphs(text_blocks, cur_page_layout)

        # 标记好标题块
        text_blocks = _sign_title_blocks(text_blocks, title_areas)
        # 替换图片部分
        if len(cur_page_images) > 0:
            text_blocks = _replace_image_area(text_blocks, cur_page_images)
        # 按块标记区域的Y,X坐标排序
        text_blocks = sorted(text_blocks, key=_images_sort)

        # 遍历所有 block 的 locations，把 page_id, page_w, page_h 写进去
        for block in text_blocks:
            if 'locations' not in block:
                continue
            for location in block['locations']:
                location['page_id'] = page_number
                location['page_w'] = int(round(page_width))
                location['page_h'] = int(round(page_height))
        result.append({"page_number": page_number, "text_blocks": text_blocks})

    chapters = _design_chapter(result)
    return chapters
