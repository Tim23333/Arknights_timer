from tools.chapter06.cold.policies import providers as base
def providers():
 p=base();r=p["reference.c6.cold_application"];p["reference.c6.cold_application"]={"evaluate":r["callable"],"version":r["version"]};return p
