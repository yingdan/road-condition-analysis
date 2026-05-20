from PIL import Image, ImageDraw

# 创建一个更清晰的公路图标
width, height = 64, 64
image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
draw = ImageDraw.Draw(image)

# 绘制公路背景（灰色）
draw.rectangle([8, 16, 56, 48], fill=(100, 100, 100))

# 绘制公路分隔线（白色）
draw.line([32, 16, 32, 48], fill=(255, 255, 255), width=3)

# 绘制路边线（白色）
draw.line([8, 16, 8, 48], fill=(255, 255, 255), width=2)
draw.line([56, 16, 56, 48], fill=(255, 255, 255), width=2)

# 绘制公路标记线（白色）
for i in range(4):
    y = 20 + i * 8
    draw.line([16, y, 28, y], fill=(255, 255, 255), width=2)
    draw.line([36, y, 48, y], fill=(255, 255, 255), width=2)

# 保存为ICO文件
image.save('road_icon.ico', format='ICO')
print('Icon created successfully!')
print('Icon size:', image.size)
print('Icon mode:', image.mode)