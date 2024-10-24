from django.shortcuts import render
from ast import Pass
from asyncio.windows_events import NULL
from cProfile import Profile
from email import message
from genericpath import exists
from itertools import product
from multiprocessing import context
from pickle import NONE

# from pyexpat.errors import messages
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .models import *
from django.contrib.auth.models import User,auth
from django.core.exceptions import ObjectDoesNotExist
# from apps.home import models
import os
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

# Create your views here.
def add(request):
    return render(request,'index.html')
def login(request):
    if  request.method=="POST":
        username=request.POST['username']
        password=request.POST['password']
        user=auth.authenticate(username=username,password=password)
        if user is not None:
                auth.login(request,user)
                return render(request,'index.html')
        else:
                msg='Invalid credentials'
    return render(request,'login.html')
def userlogout(request):
    auth.logout(request)
    # message.success(request,'Successfully Loggedout')
    return render(request,'index.html')
def signup(request):
    if(request.method=="POST"):
        first_name=request.POST['firstname']
        last_name=request.POST['lastname']
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password']
        # phonenumber=request.POST['phonenumber']
        print(first_name,last_name,username,email,password)
        myuser=User.objects.create_user(first_name=first_name,email=email,last_name=last_name,username=username,password=password)
        myuser.save()
        messages.success(request,'Created Succesfully')
        return render(request,'login.html')
    return render(request,"signup.html")
def suppliersignup(request):
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        username = request.POST['username']
        email = request.POST['email']
        contact = request.POST['contact']
        password = request.POST['password']
        confirmpassword = request.POST['comfirmpassword']
        if password != confirmpassword:
            return redirect(request, 'signup.html')
        supplier = User.objects.create(first_name=first_name,last_name=last_name,username=username,email=email,password=password)
        supplier.save()
        messages.success(request, "Supplier has been created successifully")
        return redirect(request, 'login.html')

def doctorsignup(request):
    if(request.method=="POST"):
        first_name=request.POST['firstname']
        last_name=request.POST['lastname']
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password']
        # phonenumber=request.POST['phonenumber']
        print(first_name,last_name,username,email,password)
        myuser=User.objects.create_user(first_name=first_name,email=email,last_name=last_name,username=username,password=password)
        myuser.save()
        fullname=first_name+last_name
        object=verifydoc(username=username,name=fullname)
        object.save()
        return render(request,'login.html')
    return render(request,'doctorsignup.html')
def adminpage(request):
    # Get a queryset of all superusers
    superusers = User.objects.filter(is_superuser=True)
    user = request.user
    
    # Check if the current user is in the superuser queryset
    if user in superusers:
        return render(request, 'adminpage.html')
    
    # If the user is not a superuser, redirect to the index page
    return render(request, 'index.html')

def patientpage(request):
    return render(request, 'patientpage.html')
def doctorpage(request):
    return render(request,'doctorpage.html')
def contactus(request):
    return render(request,'contactus.html')
def additem(request):
    if request.method=="POST":
        productname=request.POST['productname']
        productidnumber=request.POST['productidnumber']
        productdescrition=request.POST['productdescrition']
        productstock=request.POST['productstock']
        productprice=request.POST['productprice']
        if len(request.FILES) != 0:
            product_image=request.FILES['img[]']
        print(productname,productidnumber,productdescrition,productstock,productprice,product_image)
        object=addproduct(productname=productname,productprice=productprice,productidnumber=productidnumber,productstock=productstock,productdescrition=productdescrition,productimage=product_image)
        object.save()
        return redirect('additem')
    return render(request,'addproduct.html')

def bookappointmentpatient(request):
    user=request.user
    username = User.objects.filter(username=user)
    if(len(username)==0):
        print('ssssssssss')
        messages.error(request,'login required')
        return redirect('patientpage')
    
    doctorlist=doctoradd.objects.all()
    context={'doctorlist':doctorlist}
    if request.method=="POST":
        patientname=request.POST['patientname']
        doctorchoice=request.POST['doctorchoice']
        doctor=doctoradd.objects.get(id=doctorchoice)
        slot=request.POST['slot']
        type=request.POST['type']
        description=request.POST['somedescrition']
        user=request.user
        object=patientappoint(username=user,type=type,patientname=patientname,doctorname=doctor.doctorname,doctorspecialization=doctor.specialization,slot=slot,description=description,doctorid=doctorchoice)
        object.save()
        return render(request,'bookappointmentpatient.html',context)
    return render(request,'bookappointmentpatient.html',context)
def vediocall(request):
    user=request.user
    username = verifydoc.objects.filter(username=user)
    print(len(username))
    if (len(username)==0 ):
        messages.error(request,'Doctor login required')
        return redirect('doctorpage')
    return render(request,'vediocall.html')
def patientvidcall(request):
    return render(request,'patientvidcall.html')
def store(request):
    user=request.user
    username1=User.objects.filter(username=user)
    print(len(username1))
    if (len(username1)==0):
        messages.error(request,'login required')
        return redirect('login')
    print(user)
    product_list=addproduct.objects.all()
    print(product_list)
    print('55')
    context={'product_list':product_list}
    print('6')
    return render(request,'store.html',context)
def list(request):
    product_list= addproduct.objects.all()
    print(product_list)
    doctorlist=doctoradd.objects.all()
    context={'product_list':product_list,'doctorlist':doctorlist}
    
    return render(request,'list.html',context)
def doctoradds(request):
    if request.method=="POST":
        doctorname=request.POST['doctorname']
        specialization=request.POST['specialization']
        hospitalname=request.POST['hospitalname']
        address=request.POST['address']
        fess=request.POST['fess']
        if len(request.FILES) != 0:
            doctorimage=request.FILES['img[]']
        # print(productname,productidnumber,productdescrition,productstock,productprice,product_image)
        object=doctoradd(doctorname=doctorname,specialization=specialization,hospitalname=hospitalname,address=address,fess=fess,doctorimage=doctorimage)
        object.save()
        return redirect('doctoradd')
    return render(request,'doctoradd.html')


def addcart(request,id):
    if request.method=="POST":
        product= addproduct.objects.get(id=id)
        # print(product.product_name)
        user=request.user
        user2=user.id
        print("user.............",user)
        prod=cart()
        product_name=product.productname
        product_price=product.productprice
        # print(User.get_username)
        # prod=Cart(product_name=product_name,product_price=product_price,usercart=user)
        # prod.save()
        # print(prod)
        prod2=cart.objects.filter(usercart=user2,productname=product_name)
        prod3=cart.objects.filter(productname=product_name)
        print(".......................username:",User.get_username)
        # if not prod2:
        #     if not prod3:
        #         quantity=1
        #         prod=Cart(product_name=product_name,product_price=product_price,usercart=user,quantity=quantity)
        #         prod.save()
        print("JJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJ")
        print(prod2)
        print(user2)
        print(product_name)

        print(len(prod2))
        print(len(prod3))

        if len(prod2)>0:
            if len(prod3)>0:
                prod4= cart.objects.get(usercart=user2,productname=product_name)
                if prod4:
                    quantity=prod4.quantity
                    quantity=quantity+1
                    print(quantity)
                    prod4.quantity=quantity
                    # print(prod.quantity)
                    # prod=Cart(quantity=quantity)
                    prod4.save()
            else:
                quantity=1
                prod=cart(productname=product_name,productprice=product_price,usercart=user,quantity=quantity,username=user)
                prod.save()
        else:
                quantity=1
                prod=cart(productname=product_name,productprice=product_price,usercart=user,quantity=quantity,username=user)
                prod.save()
        

        # __________stock decrease_______
        c= addproduct.objects.get(id=id)
        c.productstock=c.productstock - 1 
        if c.productstock > 0:
            c.save()
        else:
            c.productstock=0
            c.save()

        # _______end_______

        
        return redirect('store')



def vieworders(request):
    user=request.user
    user2=user.id
    product_list= cart.objects.filter(usercart=user2)
    print(product_list)
    context={'product_list':product_list}
    # print('31')
    return render(request,'vieworders.html',context)


def remove(request, id):
    print('del1')
    # ________________________________restore stock_________________
    product=cart.objects.get(id=id)
    restore=product.quantity
    name=product.productname
    name1=addproduct.objects.get(productname=name)
    # name2=name1.product_stock
    name1.productstock=name1.productstock+product.quantity
    name1.save()
    # name2=name1.product_stock
    print("rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr")
    print(restore)
    print(name1)
    # print(name2)
    
    # _____________delete___________
    print('del12')

    product.delete()
    print('del13')

    


    # messages.success(request,"Product deleted Successfully.")
    return redirect('vieworders')
    # return render (request,'vieworders.html')


def watchappointment(request):
    user = request.user
    username = verifydoc.objects.filter(username=user.username)
    if len(username) == 0:
        messages.error(request, 'Doctor login required')
        return redirect('doctorpage')

    print("Current user:", user.username)  # Debugging line

    try:
        doctorid = doctoradd.objects.get(doctorname=user.username)
        doctorname = patientappoint.objects.filter(doctorid=doctorid.id)
    except ObjectDoesNotExist: # type: ignore
        messages.error(request, 'Doctor not found')
        return redirect('doctorpage')

    context1 = {'doctorname': doctorname}
    return render(request, 'watchappointment.html', context1)

    context1 = {'doctorname': doctorname}
    return render(request, 'watchappointment.html', context1)
def delete(request,id):
    product=patientappoint.objects.get(id=id)
    print('del12')
    product.delete()
    return redirect('watchappointment')
def deleteproduct(request,id):
    product=addproduct.objects.get(id=id)
    print('del12')
    product.delete()
    return redirect('list')
def deletedoc(request,id):
    product=doctoradd.objects.get(id=id)
    print('del12')
    product.delete()
    return redirect('list')
def updatedoc(request,id):
    prod= doctoradd.objects.get(id=id)
    context={'prod':prod}
    if request.method=="POST":
        prod.doctorname=request.POST['doctorname']
        prod.specialization=request.POST['specialization']
        prod.hospitalname=request.POST['hospitalname']
        prod.address=request.POST['address']
        prod.fess=request.POST['fess']
        print("sssssssssssssssssss",len(request.FILES))
        if len(request.FILES) != 0:
            if len(prod.doctorimage) >0:
                os.remove(prod.doctorimage.path)
            prod.doctorimage= request.FILES['img[]']
        # print(productname,productidnumber,productdescrition,productstock,productprice,product_image)
        # object=doctoradd(doctorname=doctorname,specialization=specialization,hospitalname=hospitalname,address=address,fess=fess,doctorimage=doctorimage)
        prod.save()
        return redirect('list')
    return render(request,'updatedoc.html',context)
def updateproduct(request,id):
    prod= addproduct.objects.get(id=id)
    context={'prod':prod}
    if request.method=="POST":
        prod.productname=request.POST['productname']
        prod.productprice=request.POST['productprice']
        prod.productidnumber=request.POST['productidnumber']
        prod.productstock=request.POST['productstock']
        prod.productdescrition=request.POST['productdescrition']
        print("sssssssssssssssssss",len(request.FILES))
        if len(request.FILES) != 0:
            if len(prod.productimage) >0:
                os.remove(prod.productimage.path)
            prod.productimage= request.FILES['img[]']
        # print(productname,productidnumber,productdescrition,productstock,productprice,product_image)
        # object=doctoradd(doctorname=doctorname,specialization=specialization,hospitalname=hospitalname,address=address,fess=fess,doctorimage=doctorimage)
        prod.save()
        return redirect('list')
    return render(request,'updateproduct.html',context)
def allorders(request):
    orderlist= cart.objects.all()
    context={'orderlist':orderlist}
    return render(request,'allorders.html',context)


def payment(request):
    return render(request,'payment.html')

