# coding=utf-8
from django.shortcuts import render, render_to_response
from django import forms
from django.template.context import RequestContext
import tarfile
import os

from mysite import settings
from models import softwares, graph_dbs
from django.http.response import HttpResponse
from util.sync_soft import sync_software
from django.contrib.auth.decorators import login_required
from threading import Thread
from util.database_proc import database_creat_thread
from software_manager.util.database_proc import start_neo4j_db, stop_neo4j_db,\
    is_character_db_on, start_character_db, stop_character_db
from diffHandle.models import vulnerability_info
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

# Create your views here.

class soft_info_form(forms.Form):
    soft_name = forms.CharField(label = u"软件名称", max_length = 50)
    soft_version = forms.CharField(label = u"软件版本", max_length = 20)
    source = forms.FileField(label = u"软件源码包")

def untar(file, dir):
    t = tarfile.open(file)
    if not os.path.isdir(dir):
        os.makedirs(dir)
        
    t.extractall(path = dir)
    return dir
    
def software_import(request):
    if request.method == "GET":
        soft = soft_info_form()
        return render_to_response("import_soft.html",
                                  RequestContext(request, {'soft':soft}))
    else:
        soft = soft_info_form(request.POST, request.FILES)
        if soft.is_valid():
            name = soft.cleaned_data['soft_name']
            version = soft.cleaned_data['soft_version']
            file = request.FILES['source']
            
            #upload source to tmp path
            f = open(settings.TMP_PATH + name + version, "wb")
            for chunk in file.chunks():
                f.write(chunk)
            f.close()
            
            # untar the uploaded file
            dir = untar(settings.TMP_PATH + name + version, 
                        settings.SOFTWARE_PATH + name.lower() + r"/" + name + "-" + version)
            #remove the tmp file
            os.remove(settings.TMP_PATH + name + version)
            
            #save into databases
            software = softwares(software_name = name,
                                 software_version = version,
                                 sourcecodepath = dir,
                                 user = request.user)
            #software.user = request.user
            software.save()
            
            #notify user saved success
            return HttpResponse(u"录入成功，感谢" + request.user.username + u"对我们的支持！")
        else:
            return render_to_response("import_soft.html",
                                  RequestContext(request, {'soft':soft}))

@login_required
def software_show(request):
    if request.method == "GET":
        softs = softwares.objects.all()
        pages = Paginator(softs, 20)
        page = request.GET.get("page")
        show_softs = None
        try:
            show_softs = pages.page(page)
        except PageNotAnInteger:
            show_softs = pages.page(1)
        except EmptyPage:
            show_softs = pages.page(pages.num_pages)
        
        return render_to_response("show_softs.html", RequestContext(request,{"softs":show_softs}))
    else:
        if request.POST.has_key('refresh'):
            softs = softwares.objects.all()
            pages = Paginator(softs, 20)
            page = request.GET.get("page")
            show_softs = None
            try:
                show_softs = pages.page(page)
            except PageNotAnInteger:
                show_softs = pages.page(1)
            except EmptyPage:
                show_softs = pages.page(pages.num_pages)
                
            return render_to_response("show_softs.html", RequestContext(request,{'softs':show_softs}))
                                  
        elif request.POST.has_key('sync'):
            softs = softwares.objects.all()
            infos = sync_software()
            return render_to_response("show_softs.html", RequestContext(request, 
                                                                        {
                                                                         'softs':softs,
                                                                         'infos':infos
                                                                         }))          
@login_required
def graph_db_show(request):
    if request.method == "GET":
        softs = softwares.objects.all()
        pages = Paginator(softs,20)
        page = request.GET.get("page")
        show_softs = None
        try:
            show_softs = pages.page(page)
        except PageNotAnInteger:
            show_softs = pages.page(1)
        except EmptyPage:
            show_softs = pages.page(pages.num_pages)
        return render_to_response("graph_database.html",
                                  RequestContext(request, {'softs':show_softs, "user":request.user}))
    else:
        if request.POST.has_key("create_db"):
            soft_id = int(request.POST['soft_id'])
            th = Thread(target=database_creat_thread, args=(soft_id,))
            th.start()
            
            return HttpResponse("已启动线程为该软件生成图形数据库，敬请耐心等待！")
            
def graph_manager(request):
    if request.method == "GET":
        infos = graph_dbs.objects.all()
        status = ""
        obs = vulnerability_info.objects.filter(is_in_db=True)
        if len(obs) > 0:
            if is_character_db_on():
                status = "ON"
            else:
                status = "OFF"
        else:
            status = "NO_DB"
        return render_to_response("graph_status.html", 
                                  RequestContext(request, {'infos':infos,
                                                           'status':status,
                                                           'user':request.user}))
    else:
        if request.POST.has_key('start_db'):
            soft_id = int(request.POST['start'])
            #th = Thread(target=start_neo4j_db, args=(soft_id, 7474+soft_id))
            #th.start()
            start_neo4j_db(soft_id, soft_id + 7474)
            infos = graph_dbs.objects.all()
            
            status = ""
            obs = vulnerability_info.objects.filter(is_in_db=True)
            if len(obs) > 0:
                if is_character_db_on():
                    status = "ON"
                else:
                    status = "OFF"
            else:
                status = "NO_DB"
                
            return render_to_response("graph_status.html", 
                                      RequestContext(request, {'infos':infos,
                                                                "status":status,
                                                                'user':request.user}))
        elif request.POST.has_key('stop_db'):
            soft_id = int(request.POST['stop']) 
            stop_neo4j_db(soft_id)
            infos = graph_dbs.objects.all()
            
            status = ""
            obs = vulnerability_info.objects.filter(is_in_db=True)
            if len(obs) > 0:
                if is_character_db_on():
                    status = "ON"
                else:
                    status = "OFF"
            else:
                status = "NO_DB"
                
            return render_to_response("graph_status.html", 
                                      RequestContext(request, {'infos':infos,
                                                                "status":status,
                                                                "user":request.user}))
        elif request.POST.has_key("start"):
            start_character_db()
            
            infos = graph_dbs.objects.all()
            status = ""
            obs = vulnerability_info.objects.filter(is_in_db=True)
            if len(obs) > 0:
                if is_character_db_on():
                    status = "ON"
                else:
                    status = "OFF"
            else:
                status = "NO_DB"
                
            return render_to_response("graph_status.html", 
                                      RequestContext(request, {'infos':infos,
                                                                "status":status,
                                                                "user":request.user}))
        elif request.POST.has_key("shut_down"):
            stop_character_db()
            
            infos = graph_dbs.objects.all()
            status = ""
            obs = vulnerability_info.objects.filter(is_in_db=True)
            if len(obs) > 0:
                if is_character_db_on():
                    status = "ON"
                else:
                    status = "OFF"
            else:
                status = "NO_DB"
                
            return render_to_response("graph_status.html", 
                                      RequestContext(request, {'infos':infos,
                                                               "status":status,
                                                               "user":request.user}))