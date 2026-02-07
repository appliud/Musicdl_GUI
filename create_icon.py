"""
创建音乐下载器图标
生成一个简单的音符图标
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    # 创建256x256的图像（支持的最大图标尺寸）
    size = 256
    img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 绘制圆形背景（渐变蓝色）
    center = size // 2
    radius = size // 2 - 10
    
    # 绘制背景圆
    for r in range(radius, 0, -1):
        # 蓝色渐变
        ratio = r / radius
        blue = int(100 + 100 * ratio)
        green = int(150 + 50 * ratio)
        red = int(50 + 30 * ratio)
        draw.ellipse(
            [center - r, center - r, center + r, center + r],
            fill=(red, green, blue, 255)
        )
    
    # 绘制音符符号
    # 使用白色绘制一个简化的音符
    note_color = (255, 255, 255, 255)
    
    # 音符头部（椭圆）
    head_x, head_y = 110, 170
    draw.ellipse([head_x-25, head_y-20, head_x+25, head_y+20], fill=note_color)
    
    # 音符杆
    stem_x = head_x + 20
    draw.rectangle([stem_x, head_y-100, stem_x+8, head_y-20], fill=note_color)
    
    # 音符旗帜（弯曲的线）
    flag_points = [
        (stem_x+8, head_y-100),
        (stem_x+35, head_y-90),
        (stem_x+50, head_y-80),
        (stem_x+45, head_y-60),
        (stem_x+25, head_y-70),
        (stem_x+8, head_y-80),
    ]
    draw.polygon(flag_points, fill=note_color)
    
    # 保存为ICO文件（包含多个尺寸）
    icon_sizes = [16, 32, 48, 64, 128, 256]
    icons = []
    
    for icon_size in icon_sizes:
        resized = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        icons.append(resized)
    
    # 保存ICO文件
    ico_path = 'musicdl_icon.ico'
    icons[0].save(
        ico_path,
        format='ICO',
        sizes=[(s, s) for s in icon_sizes],
        append_images=icons[1:]
    )
    
    print(f"✅ 图标已创建: {ico_path}")
    return ico_path

if __name__ == '__main__':
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("正在安装PIL库...")
        import subprocess
        subprocess.run(['pip', 'install', 'pillow'], check=True)
        from PIL import Image, ImageDraw
    
    create_icon()
    print("图标创建完成！")
