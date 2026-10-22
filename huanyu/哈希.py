import hashlib

password = "lzno1root"
random_str = "310000" #WKNQ3H

h1 = hashlib.md5(password.encode("utf-8")).hexdigest()
h2 = hashlib.md5((h1 + random_str).encode("utf-8")).hexdigest()

print("第一次MD5:", h1)
print("最终密码:", h2)