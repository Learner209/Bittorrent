import time

def timeit(func):
    # 定义一个新的函数，用于计算函数运行时间
    def wrapper(*args, **kwargs):
        start_time = time.time() # 记录函数开始时间
        result = func(*args, **kwargs) # 调用原函数，并记录返回值
        end_time = time.time() # 记录函数结束时间
        print(f'The function {func.__name__} took {(end_time - start_time):.6f} seconds to run.')
        return result # 返回原函数的返回值
    return wrapper # 返回新的函数


