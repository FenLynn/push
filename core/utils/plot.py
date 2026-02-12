
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Global color palette
mycolors = ['#E63946', '#F1FAEE', '#A8DADC', '#457B9D', '#1D3557']

def pic1_fmt(fig,axes,title='',xlabel='x',ylabel='y',rotation=15,sci_on=False):
    axes.set_title(title,fontsize=24)
    axes.grid(linestyle='--')
    axes.set_xlabel(xlabel,fontsize=18) 
    axes.set_ylabel(ylabel,fontsize=16)
    plt.setp(axes.get_xticklabels(), rotation=rotation, horizontalalignment='right')
    axes.tick_params(axis = 'y', which = 'major', labelsize = 12,top=True,right=True) 
    axes.legend(loc='best',fontsize = 16,frameon=False)
    if sci_on:
        axes.ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def pic11_fmt(fig,axes,axes2,title='',xlabel='x',ylabel1='y1',ylabel2='y2',rotation=15,sci_on=False,set_label_y_color=True):
    axes.set_title(title,fontsize=24)
    axes.grid(linestyle='--')
    axes.set_xlabel(xlabel,fontsize=18) 
    axes2.spines['left'].set_visible(False)
    if set_label_y_color:
        axes.set_ylabel(ylabel1,color=mycolors[0],fontsize=16)
        axes2.set_ylabel(ylabel2,color=mycolors[1],fontsize=16)
        axes.spines['left'].set_color(mycolors[0])
        axes2.spines['right'].set_color(mycolors[1])
        axes.tick_params(axis = 'y', which = 'major', labelsize = 12, colors=mycolors[0]) 
        axes2.tick_params(axis = 'y', which = 'major', labelsize = 12, colors=mycolors[1]) 
        axes.tick_params(top=True)
        axes2.tick_params(top=True)
    else:
        axes.set_ylabel(ylabel1,fontsize=16)
        axes2.set_ylabel(ylabel2,fontsize=16)
        axes.tick_params(axis = 'y', which = 'major', labelsize = 12) 
        axes2.tick_params(axis = 'y', which = 'major', labelsize = 12)       
        axes.tick_params(top=True)
        axes2.tick_params(top=True)         
    plt.setp(axes.get_xticklabels(), rotation=rotation, horizontalalignment='right')
    axes.legend(loc='best',fontsize = 16,frameon=False)
    if sci_on:
        axes.ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes2.ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def pic12_fmt(fig,axes,title='',xlabel='x',ylabel='y',rotation=15,sci_on=False,set_label_y_color=True):
    plt.subplots_adjust(wspace = 0, hspace = 0 )
    fig.suptitle(title,fontsize=24)
    axes[0].grid(linestyle='--')
    axes[1].grid(linestyle='--')
    axes[0].set_xlabel(xlabel,fontsize=18) 
    if set_label_y_color:
        axes[0].set_ylabel(ylabel,fontsize=16,color=mycolors[0])
        axes[1].set_ylabel(ylabel,fontsize=16,color=mycolors[1])
        axes[0].spines['left'].set_color(mycolors[0])
        axes[1].spines['right'].set_color(mycolors[1])
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[0]) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[1])
    else:
        axes[0].set_ylabel(ylabel,fontsize=16)
        axes[1].set_ylabel(ylabel,fontsize=16)
        axes[0].tick_params(axis = 'both', which = 'both', labelsize = 12) 
        axes[1].tick_params(axis = 'both', which = 'both', labelsize = 12)
    
    axes[0].tick_params(top=True,right = True)
    axes[1].tick_params(labelleft=False,labeltop=False,labelright = True,right = True,top=True)
    axes[1].yaxis.set_label_position("right")
    plt.setp(axes[0].get_xticklabels(), rotation=rotation, horizontalalignment='right')
    plt.setp(axes[1].get_xticklabels(), rotation=90, horizontalalignment='right')
    axes[0].legend(loc='best',fontsize = 12,frameon=False)
    if sci_on:
        axes[0].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes[1].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def pic21_fmt(fig,axes,title='',xlabel='x',ylabel1='y',ylabel2='y',rotation=15,sci_on=False,set_label_y_color=True):
    plt.subplots_adjust(wspace = 0, hspace = 0 )
    axes[0].set_title(title,fontsize=24)
    axes[0].grid(linestyle='--')
    axes[1].grid(linestyle='--')
    axes[1].set_xlabel(xlabel,fontsize=18) 
    if set_label_y_color:
        axes[0].set_ylabel(ylabel1,fontsize=16,color=mycolors[0])
        axes[1].set_ylabel(ylabel2,fontsize=16,color=mycolors[1])
        axes[0].spines['left'].set_color(mycolors[0])
        axes[1].spines['left'].set_color(mycolors[1])
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[0]) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[1])
    else:
        axes[0].set_ylabel(ylabel1,fontsize=16)
        axes[1].set_ylabel(ylabel2,fontsize=16)
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12)
    axes[0].tick_params(top=True,right = True)
    axes[1].tick_params(top=True,right = True)
    plt.setp(axes[1].get_xticklabels(), rotation=rotation, horizontalalignment='right')
    axes[0].legend(loc='best',fontsize = 12,frameon=False)
    axes[1].legend(loc='best',fontsize = 12,frameon=False)
    if sci_on:
        axes[0].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes[1].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def pic31_fmt(fig,axes,title='',xlabel='x',ylabel1='y',ylabel2='y2',ylabel3='y3',rotation=15,sci_on=False,set_label_y_color=True):
    plt.subplots_adjust(wspace = 0, hspace = 0 )
    axes[0].set_title(title,fontsize=24)
    axes[0].grid(linestyle='--')
    axes[1].grid(linestyle='--')
    axes[2].grid(linestyle='--')
    axes[2].set_xlabel(xlabel,fontsize=18) 
    if set_label_y_color:
        axes[0].set_ylabel(ylabel1,fontsize=16,color=mycolors[0])
        axes[1].set_ylabel(ylabel2,fontsize=16,color=mycolors[1])
        axes[2].set_ylabel(ylabel3,fontsize=16,color=mycolors[2])
        axes[0].spines['left'].set_color(mycolors[0])
        axes[1].spines['left'].set_color(mycolors[1])
        axes[2].spines['left'].set_color(mycolors[2])        
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[0]) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[1])
        axes[2].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[2])
    else:
        axes[0].set_ylabel(ylabel1,fontsize=16)
        axes[1].set_ylabel(ylabel2,fontsize=16)
        axes[2].set_ylabel(ylabel3,fontsize=16)
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12)
        axes[2].tick_params(axis = 'y', which = 'both', labelsize = 12)
    axes[0].tick_params(top=True,right = True)
    axes[1].tick_params(top=True,right = True)
    axes[2].tick_params(top=True,right = True)
    plt.setp(axes[2].get_xticklabels(), rotation=rotation, horizontalalignment='right')
    axes[0].legend(loc='best',fontsize = 12,frameon=False)
    axes[1].legend(loc='best',fontsize = 12,frameon=False)
    axes[2].legend(loc='best',fontsize = 12,frameon=False)
    if sci_on:
        axes[0].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes[1].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes[2].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def current_line(current_value,axes,color='green',xlim=[]):
    if len(xlim) == 0:
        xaxis_lim=axes.get_xlim()
    else:
        xaxis_lim=xlim
    axes.hlines(current_value,xaxis_lim[0],xaxis_lim[1],linestyle='--',linewidth=0.8,color=color,zorder=5)
