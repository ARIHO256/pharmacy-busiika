"""pharmaflex URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from .import views

urlpatterns = [
    #path('admin/', admin.site.urls),
    path('',views.add,name="add"),
    path('login',views.login,name="login"),
    path('userlogout',views.userlogout,name="userlogout"),
    path('signup',views.signup,name="signup"),
    path('doctorsignup',views.doctorsignup,name="doctorsignup"),
    path('patientpage',views.patientpage,name="patientpage"),
    path('doctorpage',views.doctorpage,name="doctorpage"),
    path('contactus',views.contactus,name="contactus"),
    path('bookappointmentpatient',views.bookappointmentpatient,name="bookappointmentpatient"),
    path('vediocall',views.vediocall,name="vediocall"),
    path('patientvidcall',views.patientvidcall,name="patientvidcall"),
    path('store',views.store,name="store"),
    path('adminpage',views.adminpage,name="adminpage"),
    path('list',views.list,name="list"),
    path('vieworders',views.vieworders,name="vieworders"),
    path('additem',views.additem,name="additem"),
    path('doctoradd',views.doctoradds,name="doctoradd"),
    path('watchappointment',views.watchappointment,name="watchappointment"),
    path('delete/<int:id>',views.delete ,name='delete'),
    path('deleteproduct/<int:id>',views.deleteproduct ,name='deleteproduct'),
    path('deletedoc/<int:id>',views.deletedoc ,name='deletedoc'),
    path('updatedoc/<int:id>',views.updatedoc ,name='updatedoc'),
    path('updateproduct/<int:id>',views.updateproduct ,name='updateproduct'),
    path('allorders',views.allorders,name="allorders"),
    path('payment',views.payment,name="payment"),
    path('addcart/<int:id>',views.addcart, name='addcart'),
    path('remove/<int:id>',views.remove ,name='remove'),



]
