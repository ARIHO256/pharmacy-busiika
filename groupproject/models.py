from django.db import models
from urllib import request
from django.db import models
from django.contrib.auth.models import User
import datetime
import os
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
# Create your models here...
class addproduct(models.Model):
    productname=models.CharField(max_length=50)
    productprice=models.IntegerField()
    productidnumber=models.IntegerField()
    productstock=models.IntegerField(default=0, blank=True, null=True)
    productdescrition=models.TextField()
    productimage=models.ImageField(upload_to="static/addproduct/image",default="")

class doctoradd(models.Model):
    doctorname=models.CharField(max_length=50)
    specialization=models.CharField(max_length=50)
    hospitalname=models.CharField(max_length=50)
    address=models.TextField()
    fess=models.IntegerField()
    doctorimage=models.ImageField(upload_to="static/doctor/image",default="")

class bookappointment(models.Model):
    # doctor field, availble doctor name, time date
    # patient payment conform name id slot
    doctorfield=models.TextField()
    availabledoctor=models.TextField()
    time=models.TimeField()
    type=models.CharField(max_length=100,default="offline")

class patientappoint(models.Model):
    username=models.CharField(max_length=100,default="")
    patientname=models.CharField(max_length=100)
    doctorname=models.CharField(max_length=100)
    doctorspecialization=models.CharField(max_length=100)
    slot=models.TextField()
    description=models.TextField()
    doctorid=models.IntegerField()
    type=models.CharField(max_length=100,default="offline")
    def __str__(self):
        return f"{self.patientname}"
    
class orders(models.Model):
    productidnumber=models.IntegerField()
    quantity=models.IntegerField()
    productname=models.CharField(max_length=50)
    def __str__(self):
        return f"{self.productname}"
class verifydoc(models.Model):
    username=models.CharField(max_length=100)
    name=models.CharField(max_length=100)
    def __str__(self):
        return f"{self.name}"
class cart(models.Model):
    productname=models.CharField(max_length=50)
    productprice=models.IntegerField()
    usercart=models.ForeignKey(User,on_delete=models.DO_NOTHING)
    username=models.CharField(max_length=50)
    quantity=models.IntegerField()
    def __str__(self):
        return f"{self.productname}"
    
class Product(models.Model):
    name = models.CharField(max_length=40, blank=True)
    description =models.TextField()
    quantity = models.IntegerField()
    price = models.IntegerField()
    
    def __str__(self):
        return self.name
    
class Supplier(models.Model):
    suppliername = models.CharField(max_length=60, blank=True)
    contact = models.IntegerField()
    email = models.EmailField(max_length=155,  blank=True, unique=True)
    address = models.TextField()
    product = models.ManyToManyField(Product, related_name='product')
    supply_date = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.suppliername 

    

    

    