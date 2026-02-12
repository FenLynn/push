
def fmt_demical(_df,column_list=[],num=2):
    for i in column_list:
        _df[i]=round(_df[i],2)
    return _df

def fmt_no(num,ndem=2):
    return round(num,2)
